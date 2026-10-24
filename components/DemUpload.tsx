"use client";

import { useRef, useState } from "react";
import { uploadDem } from "@/lib/api";

interface DemUploadProps {
  siteId: string;
  onUploaded: () => void;
}

export default function DemUpload({ siteId, onUploaded }: DemUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setMessage(null);
    setError(null);

    try {
      const result = await uploadDem(siteId, file);
      setMessage(result.message);
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }

  return (
    <div className="dem-upload">
      <label className="pick-mode-label">Upload NASA GeoTIFF DEM</label>
      <p className="site-description">
        Upload a .tif elevation file for this site. Saved locally to{" "}
        <code>data/dems/</code> for development.
      </p>
      <input
        ref={inputRef}
        type="file"
        accept=".tif,.tiff"
        onChange={handleFileChange}
        disabled={uploading || !siteId}
        className="dem-upload-input"
      />
      {uploading && <p className="loading">Uploading DEM…</p>}
      {message && <p className="status-message">{message}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
