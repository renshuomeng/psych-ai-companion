import type { ConversationSendResponse } from "../types/api";
import { apiUrl, ownerHeaders, parseJsonResponse } from "./client";

export type JobResponse = {
  job_id: string;
  session_id: string;
  status: string;
  stage: string;
  progress: number;
  result?: ConversationSendResponse | null;
  error?: Record<string, unknown> | null;
};

export async function createJob(payload: Record<string, unknown>): Promise<JobResponse> {
  const response = await fetch(apiUrl("/multimodal/jobs"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...ownerHeaders() },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const response = await fetch(apiUrl(`/multimodal/jobs/${jobId}`), {
    headers: ownerHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}

export async function cancelJob(jobId: string): Promise<JobResponse> {
  const response = await fetch(apiUrl(`/multimodal/jobs/${jobId}`), {
    method: "DELETE",
    headers: ownerHeaders(),
    credentials: "include",
  });
  return parseJsonResponse(response);
}
