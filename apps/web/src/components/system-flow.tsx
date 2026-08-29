"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  type Edge,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { cx } from "@/components/ui";

export type ProbeState = "ok" | "degraded" | "down" | "checking" | "unknown";

/** `tier` quyết định màu; nó nói NODE NÀY LÀ LOẠI GÌ, không phải nó khoẻ hay yếu. */
type Tier = "client" | "edge" | "compute" | "data" | "media" | "build";

export type ServiceData = {
  label: string;
  provider: string;
  tier: Tier;
  state: ProbeState;
  latencyMs?: number | null;
  detail?: string | null;
  index: number;
  selected: boolean;
};

const TIER_ACCENT: Record<Tier, string> = {
  client: "var(--ink-faint)",
  edge: "var(--accent-us)",
  compute: "var(--action)",
  data: "var(--accent-au)",
  media: "var(--accent-uk)",
  build: "var(--ink-faint)",
};

const STATE_TONE: Record<ProbeState, string> = {
  ok: "var(--ok)",
  degraded: "var(--warn)",
  down: "var(--alert)",
  checking: "var(--ink-faint)",
  unknown: "var(--ink-faint)",
};

const STATE_LABEL: Record<ProbeState, string> = {
  ok: "healthy",
  degraded: "degraded",
  down: "down",
  checking: "checking",
  unknown: "not checked",
};

const SIDES = [
  ["left", Position.Left],
  ["right", Position.Right],
  ["top", Position.Top],
  ["bottom", Position.Bottom],
] as const;

function ServiceNode({ data }: NodeProps<Node<ServiceData>>) {
  const accent = TIER_ACCENT[data.tier];
  const tone = STATE_TONE[data.state];
  return (
    <div
      className={cx(
        "sysnode w-[210px] cursor-pointer rounded border bg-panel transition-colors",
        data.selected ? "border-action" : "border-rule-strong hover:border-rule-strong/80",
      )}
      style={{ ["--accent" as string]: accent, animationDelay: `${data.index * 70}ms` }}
    >
      {/* Mỗi cạnh cần CẢ source LẪN target. Chỉ khai source thì mọi cạnh trỏ vào
          node này không nối được, và React Flow bỏ vẽ chúng — sơ đồ thành một
          đám ô rời mà không có lỗi nào. */}
      {SIDES.map(([id, position]) => (
        <span key={id}>
          <Handle id={`s-${id}`} type="source" position={position} className="sysport" />
          <Handle id={`t-${id}`} type="target" position={position} className="sysport" />
        </span>
      ))}
      <div className="h-1 rounded-t" style={{ background: `rgb(${accent})` }} />
      <div className="px-3 py-2.5">
        <div className="flex items-start justify-between gap-2">
          <p className="font-display text-small font-semibold leading-tight text-ink">
            {data.label}
          </p>
          <span
            className={cx(
              "sysdot mt-0.5 h-2 w-2 shrink-0 rounded",
              data.state === "ok" && "is-live",
            )}
            style={{ background: `rgb(${tone})` }}
            aria-label={STATE_LABEL[data.state]}
          />
        </div>
        <p className="mt-1 truncate font-mono text-[11px] leading-4 text-ink-faint">
          {data.provider}
        </p>
        {(data.latencyMs != null || data.detail) && (
          <p
            className="mt-1.5 font-mono text-[11px] leading-4 tabular-nums"
            style={{ color: `rgb(${tone})` }}
          >
            {data.latencyMs != null ? `${Math.round(data.latencyMs)} ms` : data.detail}
          </p>
        )}
      </div>
    </div>
  );
}

const nodeTypes = { service: ServiceNode };

export function SystemFlow({
  nodes,
  edges,
  onSelect,
}: {
  nodes: Node<ServiceData>[];
  edges: Edge[];
  onSelect: (id: string) => void;
}) {
  return (
    <div className="sysflow h-[560px] w-full overflow-hidden rounded border border-rule-strong bg-recess">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        colorMode="system"
        fitView
        fitViewOptions={{ padding: 0.14 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        edgesFocusable={false}
        minZoom={0.4}
        maxZoom={1.6}
        onNodeClick={(_, node) => onSelect(node.id)}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
