import React, { useCallback, useEffect } from 'react';
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  MarkerType,
  Background,
  Controls,
} from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface LearningMapProps {
  onLessonSelect: (lessonId: string) => void;
}

const LearningMap: React.FC<LearningMapProps> = ({ onLessonSelect }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    const fetchMap = async () => {
      try {
        const response = await fetch('http://localhost:8005/map/student_beta_1');
        const data = await response.json();
        
        // Transform Neo4j data to React Flow nodes/edges
        const prereqSources = new Set(data.links.filter((l: any) => l.type === 'PREREQUISITE').map((l: any) => l.source));

        const flowNodes: Node[] = data.nodes.map((n: any, index: number) => {
          const isLocked = prereqSources.has(n.id) && !n.labels.includes('Subject');
          
          return {
            id: n.id,
            data: { 
              label: n.properties.title || n.id,
              conceptId: n.properties.id,
              labels: n.labels,
              isLocked
            },
            position: { x: index * 200, y: (index % 3) * 100 }, // Basic layout for MVP
            style: { 
              background: n.labels.includes('Subject') ? '#3b82f6' : '#fff',
              color: n.labels.includes('Subject') ? '#fff' : '#000',
              borderRadius: '8px',
              padding: '10px',
              width: 150,
              textAlign: 'center' as const,
              border: isLocked ? '2px dashed #94a3b8' : '2px solid #2563eb',
              opacity: isLocked ? 0.6 : 1,
              cursor: isLocked ? 'not-allowed' : 'pointer'
            },
          };
        });

        const flowEdges: Edge[] = data.links.map((l: any, index: number) => ({
          id: `e-${index}`,
          source: l.source,
          target: l.target,
          label: l.type,
          animated: l.type === 'PREREQUISITE',
          markerEnd: { type: MarkerType.ArrowClosed },
        }));

        setNodes(flowNodes);
        setEdges(flowEdges);
      } catch (error) {
        console.error("Failed to fetch curriculum map:", error);
        
        // Fallback mock data if service is not running
        const mockNodes: Node[] = [
          { id: 'math-8', data: { label: '8th Grade Math' }, position: { x: 0, y: 0 }, type: 'input' },
          { id: 'math-8-alg', data: { label: 'Algebra Unit' }, position: { x: 0, y: 100 } },
          { id: 'math-8-alg-1', data: { label: 'One-Step Equations' }, position: { x: -150, y: 200 } },
          { id: 'math-8-alg-2', data: { label: 'Two-Step Equations' }, position: { x: 0, y: 300 } },
          { id: 'math-8-alg-3', data: { label: 'Variables on Both Sides' }, position: { x: 150, y: 200 } },
        ];
        const mockEdges: Edge[] = [
          { id: 'e1', source: 'math-8', target: 'math-8-alg' },
          { id: 'e2', source: 'math-8-alg', target: 'math-8-alg-1' },
          { id: 'e3', source: 'math-8-alg-1', target: 'math-8-alg-2', animated: true },
          { id: 'e4', source: 'math-8-alg', target: 'math-8-alg-3' },
        ];
        setNodes(mockNodes);
        setEdges(mockEdges);
      }
    };

    fetchMap();
  }, [setNodes, setEdges]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    const conceptId = (node.data?.conceptId as string) || node.id;
    const labels = (node.data?.labels as string[]) || [];
    const isLocked = node.data?.isLocked;

    if (isLocked) {
      alert("This lesson is locked! Please complete the prerequisites first.");
      return;
    }

    // Support Lessons, Concepts, Units (like Introduction to Algebra), or any math-8 IDs
    if (
      labels.includes('Lesson') || 
      labels.includes('Concept') || 
      labels.includes('Unit') || 
      conceptId.includes('alg')
    ) {
       onLessonSelect(conceptId);
    }
  }, [onLessonSelect]);

  return (
    <div style={{ width: '100%', height: '80vh', background: '#f8fafc', borderRadius: '12px', overflow: 'hidden' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
};

export default LearningMap;
