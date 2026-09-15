import { agents } from "@/lib/mock-data/agents";
import { executions } from "@/lib/mock-data/executions";
import { files } from "@/lib/mock-data/files";
import { knowledgeSources } from "@/lib/mock-data/knowledge";
import { tasks } from "@/lib/mock-data/tasks";
import { workflows } from "@/lib/mock-data/workflows";

/*
 * Static params for `output: export`.
 *
 * We pre-render every known seed entity. Tasks (and other entities) created at
 * runtime inside the SPA are reached via client-side navigation, which renders
 * the same [id] component in the browser without a server round trip — so only
 * seed IDs need static generation for a cold full-page load.
 */
export const taskParams = () => tasks.map((t) => ({ id: t.id }));
export const agentParams = () => agents.map((a) => ({ id: a.id }));
export const workflowParams = () => workflows.map((w) => ({ id: w.id }));
export const executionParams = () => executions.map((e) => ({ id: e.id }));
export const knowledgeParams = () => knowledgeSources.map((k) => ({ id: k.id }));
export const fileParams = () => files.map((f) => ({ id: f.id }));
