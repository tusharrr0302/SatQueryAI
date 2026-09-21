<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as echarts from 'echarts';
  import 'echarts-gl';

  export let type: string = 'line';
  export let title: string = '';
  export let subTitle: string = '';
  export let data: any[] | undefined = undefined;
  export let xAxis: any = undefined;
  export let yAxis: any = undefined;
  export let series: any[] | undefined = undefined;
  export let visualMap: any = undefined;
  export let height: string = '100%';

  let chartContainer: HTMLDivElement;
  let chart: echarts.ECharts | null = null;
  let resizeObserver: ResizeObserver | null = null;

  $: if (chart && (type || title || subTitle || data || xAxis || yAxis || series || visualMap)) {
    buildAndRender();
  }

  onMount(() => {
    if (!chartContainer) return;
    try {
      chart = echarts.init(chartContainer, 'dark', { renderer: 'canvas' });
      buildAndRender();

      if (window.ResizeObserver) {
        resizeObserver = new ResizeObserver(() => {
          chart?.resize();
        });
        resizeObserver.observe(chartContainer);
      }
    } catch (err) {
      console.error('EChartRenderer init error:', err);
    }
  });

  onDestroy(() => {
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
    if (chart) {
      chart.dispose();
      chart = null;
    }
  });

  export function resize() {
    chart?.resize();
  }

  function buildAndRender() {
    if (!chart) return;
    chart.clear();

    const chartType = (type || 'line').toLowerCase();

    if (chartType === '3d_surface' || chartType === 'surface' || chartType === '3d surface') {
      const surfaceData: [number, number, number][] = [];
      if (Array.isArray(data) && data.length > 0 && Array.isArray(data[0])) {
        for (let r = 0; r < data.length; r++) {
          for (let c = 0; c < data[r].length; c++) {
            surfaceData.push([c, r, data[r][c]]);
          }
        }
      } else if (Array.isArray(data) && data.length > 0 && Array.isArray(data[0]?.value)) {
        data.forEach((d: any) => surfaceData.push(d.value));
      } else if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'object' && 'x' in data[0]) {
        data.forEach((d: any) => surfaceData.push([d.x, d.y, d.z ?? d.value]));
      } else {
        // Strict scientific integrity: do not fabricate synthetic surface math
        chart.clear();
        return;
      }

      if (!surfaceData.length) {
        chart.clear();
        return;
      }

      const gradientColors = ['#111827', '#374151', '#6b7280', '#9ca3af', '#e5e7eb', '#f8fafc'];
      chart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          backgroundColor: '#0f172a',
          borderColor: 'rgba(255,255,255,0.15)',
          textStyle: { color: '#f8fafc', fontSize: 11 },
          formatter: (params: any) => {
            if (!params.data) return '';
            const [lon, lat, val] = params.data;
            return `<strong>Grid (${lon}, ${lat})</strong><br/>Surface Index: <span style="color:#e5e7eb">${val}</span>`;
          }
        },
        visualMap: {
          show: true,
          dimension: 2,
          min: -0.2,
          max: 0.8,
          inRange: { color: gradientColors },
          text: ['High', 'Low'],
          textStyle: { color: '#94a3b8', fontSize: 10 },
          bottom: 8,
          left: 10,
          itemWidth: 10,
          itemHeight: 70,
        },
        xAxis3D: {
          type: 'value',
          name: 'Lon Grid',
          nameTextStyle: { color: '#94a3b8', fontSize: 10 },
          axisLine: { lineStyle: { color: 'rgba(255,255,255,0.15)' } },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        },
        yAxis3D: {
          type: 'value',
          name: 'Lat Grid',
          nameTextStyle: { color: '#94a3b8', fontSize: 10 },
          axisLine: { lineStyle: { color: 'rgba(255,255,255,0.15)' } },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        },
        zAxis3D: {
          type: 'value',
          name: 'Index',
          min: -0.2,
          max: 0.8,
          nameTextStyle: { color: '#e5e7eb', fontSize: 10 },
          axisLine: { lineStyle: { color: 'rgba(255,255,255,0.15)' } },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        },
        grid3D: {
          boxWidth: 100,
          boxDepth: 95,
          boxHeight: 38,
          light: {
            main: { intensity: 1.2, shadow: true },
            ambient: { intensity: 0.5 }
          },
          viewControl: {
            autoRotate: true,
            autoRotateSpeed: 6,
            beta: 35,
            alpha: 28,
            distance: 190,
            panSensitivity: 1,
            rotateSensitivity: 1,
          }
        },
        series: [
          {
            type: 'surface',
            wireframe: {
              show: true,
              lineStyle: { color: 'rgba(0, 0, 0, 0.25)', width: 0.5 }
            },
            shading: 'color',
            data: surfaceData
          }
        ]
      });
      return;
    }

    const isPieOrDonut = chartType === 'pie' || chartType === 'donut';
    const isHeatmap = chartType === 'heatmap';
    const isRadar = chartType === 'radar';

    // 1. Build xAxis configuration
    let resolvedXAxis: any = undefined;
    if (!isPieOrDonut && !isRadar) {
      if (xAxis) {
        resolvedXAxis = {
          ...xAxis,
          axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.15)' }, ...xAxis.axisLine },
          axisLabel: { color: '#94a3b8', fontSize: 11, ...xAxis.axisLabel },
          splitLine: xAxis.splitLine || { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
        };
      } else if (chartType === 'scatter') {
        resolvedXAxis = {
          type: 'value',
          splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.07)' } },
          axisLabel: { color: '#94a3b8', fontSize: 11 },
        };
      } else if (data && data.length > 0) {
        const categories = data.map((d: any) => {
          const raw = d.date || d.label || d.name || String(d);
          return typeof raw === 'string' && raw.length >= 10 ? raw.slice(0, 10) : raw;
        });
        resolvedXAxis = {
          type: 'category',
          data: categories,
          axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.15)' } },
          axisLabel: { color: '#94a3b8', fontSize: 11 },
        };
      } else {
        resolvedXAxis = { type: 'category', data: [] };
      }
    }

    // 2. Build yAxis configuration
    let resolvedYAxis: any = undefined;
    if (!isPieOrDonut && !isRadar) {
      if (yAxis) {
        resolvedYAxis = {
          ...yAxis,
          axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.15)' }, ...yAxis.axisLine },
          axisLabel: { color: '#94a3b8', fontSize: 11, ...yAxis.axisLabel },
          splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.06)' }, ...yAxis.splitLine },
        };
      } else {
        resolvedYAxis = {
          type: 'value',
          axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.15)' } },
          axisLabel: { color: '#94a3b8', fontSize: 11 },
          splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } },
        };
      }
    }

    // 3. Build Series configuration
    let resolvedSeries: any[] = [];
    if (series && series.length > 0) {
      resolvedSeries = series.map((s: any) => {
        const sType = s.type || (chartType === 'histogram' ? 'bar' : chartType === 'area' ? 'line' : chartType === 'donut' ? 'pie' : chartType);
        const item: any = {
          ...s,
          type: sType,
        };
        if (sType === 'line') {
          item.smooth = s.smooth !== undefined ? s.smooth : true;
          item.symbolSize = s.symbolSize || 6;
          if (chartType === 'area' && !item.areaStyle) {
            item.areaStyle = { color: 'rgba(56, 189, 248, 0.2)' };
          }
        } else if (sType === 'bar') {
          item.barMaxWidth = s.barMaxWidth || 42;
          item.itemStyle = {
            borderRadius: [4, 4, 0, 0],
            ...s.itemStyle,
          };
        } else if (sType === 'pie') {
          if (chartType === 'donut' && !item.radius) {
            item.radius = ['42%', '72%'];
          }
        }
        return item;
      });
    } else if (data && data.length > 0) {
      if (isPieOrDonut) {
        const pieItems = data.map((d: any) => ({
          name: d.name || d.label || 'Class',
          value: d.value !== undefined ? d.value : d,
          itemStyle: d.itemStyle,
        }));
        resolvedSeries = [
          {
            name: title || 'Surface Proportion',
            type: 'pie',
            radius: chartType === 'donut' ? ['42%', '70%'] : '65%',
            avoidLabelOverlap: true,
            itemStyle: { borderRadius: 6, borderColor: '#080c14', borderWidth: 2 },
            label: {
              show: true,
              color: '#94a3b8',
              fontSize: 11,
              formatter: '{b}: {d}%',
            },
            data: pieItems,
          },
        ];
      } else if (chartType === 'bar' || chartType === 'histogram') {
        const values = data.map((d: any) => (d.value !== undefined ? d.value : d));
        resolvedSeries = [
          {
            type: 'bar',
            data: values,
            barMaxWidth: 42,
            itemStyle: {
              color: '#38bdf8',
              borderRadius: [4, 4, 0, 0],
            },
          },
        ];
      } else if (chartType === 'scatter') {
        const values = data.map((d: any) => (d.value !== undefined ? d.value : d));
        resolvedSeries = [
          {
            type: 'scatter',
            data: values,
            symbolSize: 8,
            itemStyle: { color: '#38bdf8' },
          },
        ];
      } else {
        // Line / Area default
        const values = data.map((d: any) => (d.value !== undefined ? d.value : d));
        resolvedSeries = [
          {
            type: 'line',
            data: values,
            smooth: true,
            symbolSize: 6,
            itemStyle: { color: '#e5e7eb' },
            lineStyle: { width: 3, color: '#e5e7eb' },
            areaStyle: chartType === 'area' ? { color: 'rgba(255, 255, 255, 0.12)' } : undefined,
          },
        ];
      }
    }

    // 4. Build ECharts Options
    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      title: title
        ? {
            text: title,
            subtext: subTitle,
            left: 10,
            top: 6,
            textStyle: {
              color: '#f8fafc',
              fontSize: 13,
              fontWeight: 600,
            },
            subtextStyle: {
              color: '#94a3b8',
              fontSize: 11,
            },
          }
        : undefined,
      legend:
        resolvedSeries.length > 1 || isPieOrDonut
          ? {
              top: title ? (subTitle ? 34 : 26) : 6,
              right: 12,
              textStyle: { color: '#94a3b8', fontSize: 11 },
              itemWidth: 12,
              itemHeight: 8,
            }
          : undefined,
      tooltip: {
        trigger: isPieOrDonut || chartType === 'scatter' ? 'item' : 'axis',
        backgroundColor: '#0d1527',
        borderColor: 'rgba(56, 189, 248, 0.4)',
        borderWidth: 1,
        textStyle: { color: '#f8fafc', fontSize: 12 },
        padding: [8, 12],
        formatter: (params: any) => {
          const point = Array.isArray(params) ? params[0] : params;
          const raw = data?.[point?.dataIndex];
          const date = raw?.date || point?.axisValue || '';
          const value = Number(raw?.value ?? point?.value);
          const metric = raw?.metric_name || raw?.unit || 'Observed value';
          return `<strong>${date}</strong><br/>${metric}: <b>${Number.isFinite(value) ? value.toFixed(4) : 'Unavailable'}</b>`;
        },
      },
      grid: isPieOrDonut
        ? undefined
        : {
            top: title ? (subTitle ? 56 : 44) : 20,
            right: 18,
            bottom: isHeatmap ? 45 : 30,
            left: 45,
            containLabel: true,
          },
      xAxis: resolvedXAxis,
      yAxis: resolvedYAxis,
      series: resolvedSeries,
      visualMap: visualMap,
    };

    chart.setOption(option, true);
  }
</script>

<div class="echart-renderer-container" style="height: {height};">
  <div bind:this={chartContainer} class="chart-box"></div>
</div>

<style>
  .echart-renderer-container {
    width: 100%;
    position: relative;
    overflow: hidden;
  }

  .chart-box {
    width: 100%;
    height: 100%;
    min-height: 200px;
  }
</style>
