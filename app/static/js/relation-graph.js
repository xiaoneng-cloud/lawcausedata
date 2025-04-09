// 条文关联图谱初始化
function initRelationGraph(regulations, structures, causes) {
    // 准备节点和连接数据
    const nodes = [];
    const links = [];
    
    // 添加条文节点
    structures.forEach(structure => {
        nodes.push({
            id: `s${structure.id}`,
            name: `第${structure.article}条`,
            type: 'structure',
            isViolation: structure.is_violation,
            isPenalty: structure.is_penalty,
            causeCount: structure.cause_count
        });
    });
    
    // 添加事由节点
    causes.forEach(cause => {
        nodes.push({
            id: `c${cause.id}`,
            name: cause.code,
            description: cause.description,
            type: 'cause',
            severity: cause.severity
        });
    });
    
    // 创建连接
    structures.forEach(structure => {
        if (structure.related_causes && structure.related_causes.length > 0) {
            structure.related_causes.forEach(cause => {
                links.push({
                    source: `s${structure.id}`,
                    target: `c${cause.id}`,
                    type: structure.is_violation ? 'violation' : 
                           structure.is_penalty ? 'penalty' : 'reference'
                });
            });
        }
    });
    
    // 初始化D3力导向图
    const width = document.getElementById('relation-graph').clientWidth;
    const height = 700;
    
    const svg = d3.select('#relation-graph')
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    // 创建箭头标记
    svg.append('defs').selectAll('marker')
        .data(['violation', 'penalty', 'reference'])
        .enter().append('marker')
        .attr('id', d => `arrow-${d}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', d => d === 'violation' ? '#f44336' : 
                         d === 'penalty' ? '#2196f3' : '#4caf50');
    
    // 创建模拟
    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2));
    
    // 创建连接线
    const link = svg.append('g')
        .selectAll('line')
        .data(links)
        .enter().append('line')
        .attr('stroke', d => d.type === 'violation' ? '#f44336' : 
                           d.type === 'penalty' ? '#2196f3' : '#4caf50')
        .attr('stroke-width', 2)
        .attr('marker-end', d => `url(#arrow-${d.type})`);
    
    // 创建节点
    const node = svg.append('g')
        .selectAll('.node')
        .data(nodes)
        .enter().append('g')
        .attr('class', 'node')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));
    
    // 为不同类型的节点添加不同的形状
    node.each(function(d) {
        const g = d3.select(this);
        
        if (d.type === 'structure') {
            // 条文节点使用矩形
            g.append('rect')
                .attr('width', 30)
                .attr('height', 30)
                .attr('rx', 5)
                .attr('ry', 5)
                .attr('fill', '#f8f9fa')
                .attr('stroke', d.isViolation ? '#f44336' : 
                              d.isPenalty ? '#2196f3' : '#1a3c6e')
                .attr('stroke-width', 2);
            
            // 条文编号
            g.append('text')
                .attr('dy', 20)
                .attr('dx', 15)
                .attr('text-anchor', 'middle')
                .attr('font-size', '10px')
                .attr('font-weight', 'bold')
                .text(d.name.replace(/第|条/g, ''));
        } else {
            // 事由节点使用圆形
            g.append('circle')
                .attr('r', 15)
                .attr('fill', d.severity === '轻微' ? '#e8f5e9' :
                            d.severity === '一般' ? '#fff8e1' :
                            d.severity === '严重' ? '#ffebee' : '#b71c1c')
                .attr('stroke', d.severity === '轻微' ? '#388e3c' :
                              d.severity === '一般' ? '#ffa000' :
                              d.severity === '严重' ? '#d32f2f' : '#b71c1c')
                .attr('stroke-width', 2);
            
            // 事由编号
            g.append('text')
                .attr('dy', 4)
                .attr('text-anchor', 'middle')
                .attr('font-size', '10px')
                .attr('font-weight', 'bold')
                .text(d => d.name.length > 4 ? d.name.substring(0, 3) + '…' : d.name);
        }
        
        // 添加工具提示
        g.append('title')
            .text(d => d.type === 'structure' ? 
                 `第${d.name}条 (关联事由: ${d.causeCount})` : 
                 `${d.name}: ${d.description}`);
    });
    
    // 更新节点和连接位置
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        node.attr('transform', d => `translate(${d.x - 15},${d.y - 15})`);
    });
    
    // 拖拽功能
    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }
    
    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }
    
    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
    
    // 添加图例
    const legend = svg.append('g')
        .attr('class', 'legend')
        .attr('transform', 'translate(20,20)');
    
    const legendData = [
        { color: '#1a3c6e', stroke: '#1a3c6e', text: '条文', type: 'rect' },
        { color: '#f44336', stroke: '#f44336', text: '违则条款', type: 'rect' },
        { color: '#2196f3', stroke: '#2196f3', text: '罚则条款', type: 'rect' },
        { color: '#e8f5e9', stroke: '#388e3c', text: '轻微事由', type: 'circle' },
        { color: '#fff8e1', stroke: '#ffa000', text: '一般事由', type: 'circle' },
        { color: '#ffebee', stroke: '#d32f2f', text: '严重事由', type: 'circle' },
    ];
    
    const legendItems = legend.selectAll('.legend-item')
        .data(legendData)
        .enter().append('g')
        .attr('class', 'legend-item')
        .attr('transform', (d, i) => `translate(0,${i * 25})`);
    
    legendItems.each(function(d) {
        const g = d3.select(this);
        
        if (d.type === 'rect') {
            g.append('rect')
                .attr('width', 15)
                .attr('height', 15)
                .attr('fill', '#f8f9fa')
                .attr('stroke', d.stroke)
                .attr('stroke-width', 2);
        } else {
            g.append('circle')
                .attr('cx', 7.5)
                .attr('cy', 7.5)
                .attr('r', 7.5)
                .attr('fill', d.color)
                .attr('stroke', d.stroke)
                .attr('stroke-width', 2);
        }
        
        g.append('text')
            .attr('x', 25)
            .attr('y', 12)
            .text(d.text);
    });
}