/** Ids of the nodes shipped in temporal.json. One fetch, shared by every caller. */
let nodeIds: Promise<Set<string>> | null = null;

export type StoryPlacement = "gpu" | "sigma" | "unknown";

export function temporalNodeIds(): Promise<Set<string>> {
  if (!nodeIds) {
    nodeIds = fetch("/data/views/temporal.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<{ nodes?: { id: string }[] }>;
      })
      .then((data) => {
        const ids = new Set<string>();
        for (const node of data.nodes ?? []) ids.add(node.id.toLowerCase());
        return ids;
      });
  }
  return nodeIds;
}

/** `gpu` when the topic is one of the 1,000 temporal nodes, `sigma` when it is not. */
export async function placeNamedTopic(topicId: string): Promise<StoryPlacement> {
  try {
    const ids = await temporalNodeIds();
    return ids.has(topicId.toLowerCase()) ? "gpu" : "sigma";
  } catch {
    return "unknown";
  }
}
