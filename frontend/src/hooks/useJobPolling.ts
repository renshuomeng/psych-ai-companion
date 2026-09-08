import { useEffect, useState } from "react";

import { getJob, type JobResponse } from "../api/jobs";

export function useJobPolling(jobId: string | null) {
  const [job, setJob] = useState<JobResponse | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    const refresh = () => {
      getJob(jobId)
        .then((data) => {
          if (cancelled) return;
          setJob(data);
          if (["completed", "failed", "cancelled"].includes(data.status)) {
            window.clearInterval(interval);
          }
        })
        .catch(() => undefined);
    };
    const interval = window.setInterval(refresh, 1500);
    refresh();

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [jobId]);

  return job;
}
