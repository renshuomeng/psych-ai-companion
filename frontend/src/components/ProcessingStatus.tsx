type ProcessingStatusProps = {
  status: string;
};

export default function ProcessingStatus({ status }: ProcessingStatusProps) {
  return <span className={`status-chip status-${status}`}>{status}</span>;
}
