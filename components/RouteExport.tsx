"use client";

interface RouteExportProps {
  csvData: string | null;
  onSave: () => void;
  saveMessage: string | null;
  disabled: boolean;
  inline?: boolean;
}

export default function RouteExport({
  csvData,
  onSave,
  saveMessage,
  disabled,
  inline = false,
}: RouteExportProps) {
  function downloadCsv() {
    if (!csvData) return;

    const blob = new Blob([csvData], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "icaros_route.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  if (inline) {
    return (
      <div className="export-inline">
        <button
          className="secondary btn-compact"
          onClick={downloadCsv}
          disabled={disabled || !csvData}
        >
          Download CSV
        </button>
        <button className="secondary btn-compact" onClick={onSave} disabled={disabled}>
          Save Run
        </button>
        {saveMessage && <span className="export-inline-msg">{saveMessage}</span>}
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Export</h2>
      </div>
      <div className="export-row">
        <button
          className="secondary"
          onClick={downloadCsv}
          disabled={disabled || !csvData}
        >
          Download CSV
        </button>
        <button className="secondary" onClick={onSave} disabled={disabled}>
          Save Run
        </button>
      </div>
      {saveMessage && (
        <p className="status-message export-status">{saveMessage}</p>
      )}
    </div>
  );
}
