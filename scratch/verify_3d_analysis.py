import subprocess, time, json, urllib.request
import asyncio, base64

async def main():
    chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    proc = subprocess.Popen([
        chrome_path,
        '--headless=new',
        '--remote-debugging-port=9222',
        '--no-first-run',
        '--no-default-browser-check',
        '--window-size=1440,900',
        'http://localhost:5173/'
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        ws_url = None
        for _ in range(12):
            await asyncio.sleep(1)
            try:
                with urllib.request.urlopen('http://localhost:9222/json', timeout=2) as resp:
                    tabs = json.loads(resp.read().decode('utf-8'))
                    for t in tabs:
                        if 'localhost:5173' in t.get('url', ''):
                            ws_url = t.get('webSocketDebuggerUrl')
                            break
                    if ws_url:
                        break
            except Exception:
                continue

        if not ws_url:
            print("Could not find WebSocket URL for localhost:5173")
            return

        print(f"Connected to Chrome page: {ws_url}")
        import websockets
        async with websockets.connect(ws_url) as ws:
            msg_id = 1
            async def send_cmd(method, params=None):
                nonlocal msg_id
                cmd = {"id": msg_id, "method": method, "params": params or {}}
                msg_id += 1
                await ws.send(json.dumps(cmd))
                while True:
                    res = json.loads(await ws.recv())
                    if res.get("id") == cmd["id"]:
                        return res.get("result", {})

            await send_cmd("Page.enable")
            await send_cmd("Runtime.enable")
            await asyncio.sleep(2)

            # Click on first sample query chip
            click_expr = """
            (() => {
                const buttons = Array.from(document.querySelectorAll('.sample-chip, button'));
                const chip = buttons.find(b => b.textContent.includes('Amazon') || b.textContent.includes('crop health'));
                if (chip) {
                    chip.click();
                    return 'clicked chip: ' + chip.textContent.trim();
                }
                const input = document.querySelector('.query-input, input');
                if (input) {
                    input.value = 'How has NDVI changed in the Mau Forest over the last 3 years?';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    const btn = document.querySelector('.submit-btn, button[type=\"submit\"]');
                    if (btn) btn.click();
                    return 'submitted input';
                }
                return 'no button found';
            })()
            """
            eval_res = await send_cmd("Runtime.evaluate", {"expression": click_expr})
            print("Query execution:", eval_res.get("result", {}).get("value"))

            # Wait 5 seconds for results to load
            await asyncio.sleep(5)

            # Click 3D mode button in ScientificVisPanel
            click_3d_expr = """
            (() => {
                const dimBtns = Array.from(document.querySelectorAll('.dim-btn'));
                const btn3d = dimBtns.find(b => b.textContent.includes('3D'));
                if (btn3d) {
                    btn3d.click();
                    return 'switched to 3D surface mesh';
                }
                return 'no 3d button';
            })()
            """
            eval_3d = await send_cmd("Runtime.evaluate", {"expression": click_3d_expr})
            print("3D Switch:", eval_3d.get("result", {}).get("value"))

            await asyncio.sleep(2)

            # Capture screenshot
            ss = await send_cmd("Page.captureScreenshot", {"format": "png"})
            data = base64.b64decode(ss.get("data", ""))
            out_path = "/Users/tusharrr0302/.gemini/antigravity-ide/brain/531aeb44-2941-4376-8a5b-d1e1d533399c/satquery_3d_analysis_active.png"
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"Saved screenshot ({len(data)} bytes) to {out_path}")

    finally:
        proc.terminate()

if __name__ == '__main__':
    asyncio.run(main())
