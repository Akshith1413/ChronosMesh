import { DAGData, DAGNode, DAGEdge } from '../../types';

/** Imperative controls shared by the 2D and 3D graph views. */
export interface GraphHandle {
  zoomIn(): void;
  zoomOut(): void;
  reset(): void;
}

export interface HoverInfo {
  node: DAGNode;
  x: number;
  y: number;
}

export interface GraphViewProps {
  dagData: DAGData;
  selectedNodeId?: string | null;
  highlightedPath: string[];
  invalidatedNodeIds: string[];
  removedNodeId: string | null;
  anomalyNodeIds: string[];
  rootCauseNodeIds: string[];
  flow: boolean;
  onSelectNode: (node: DAGNode) => void;
  onSelectEdge?: (edge: DAGEdge) => void;
  onHover: (info: HoverInfo | null) => void;
}
