import { NODES } from "@/lib/api";

export default function Nodes({ route = [], currentCode = null }) {
  const items = route.length ? route : NODES.map((code) => ({ code, status: "locked" }));
  return (
    <div className="nodes" data-testid="protocol-nodes">
      {items.map((node, index) => {
        const isCurrent = node.code === currentCode || (currentCode == null && node.status === "active");
        const isDone = node.status === "completed";
        return (
          <div className={`node ${isDone ? "done" : ""} ${isCurrent ? "current" : ""} ${!isDone && !isCurrent ? "locked" : ""}`} key={`${node.code}-${index}`}>
            <span>{node.code || "?"}</span>
          </div>
        );
      })}
    </div>
  );
}
