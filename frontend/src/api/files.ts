import { apiUrl, authHeaders, getStoredAuthToken, parseJsonResponse } from "./client";
import type { FileKind, UploadedFile } from "../types/api";

export function uploadFile(
  file: File,
  sessionId: string,
  kind: FileKind,
  onProgress: (progress: number) => void,
): Promise<UploadedFile> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    form.append("session_id", sessionId);
    form.append("kind", kind);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = async () => {
      const response = new Response(xhr.responseText, {
        status: xhr.status,
        headers: { "Content-Type": "application/json" },
      });
      try {
        resolve(await parseJsonResponse<UploadedFile>(response));
      } catch (error) {
        reject(error);
      }
    };
    xhr.onerror = () => reject(new Error("上传失败，请检查后端服务。"));
    xhr.withCredentials = true;
    xhr.open("POST", apiUrl("/files/upload"));
    Object.entries(authHeaders()).forEach(([key, value]) => xhr.setRequestHeader(key, value));
    xhr.send(form);
  });
}

export async function deleteFile(fileId: string, sessionId: string): Promise<void> {
  const response = await fetch(
    apiUrl(`/files/${fileId}?session_id=${encodeURIComponent(sessionId)}`),
    { method: "DELETE", credentials: "include", headers: authHeaders() },
  );
  await parseJsonResponse(response);
}

export function previewUrl(fileId: string, sessionId: string): string {
  const token = getStoredAuthToken();
  const query = new URLSearchParams({ session_id: sessionId });
  if (token) query.set("access_token", token);
  return apiUrl(`/files/${fileId}/preview?${query.toString()}`);
}
