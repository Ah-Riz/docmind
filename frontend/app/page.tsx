"use client";

import { FormEvent, useEffect, useState } from "react";

const ANALYZE_STEPS = [
  "Fetching on-chain data…",
  "Decoding instructions…",
  "Generating AI explanation…",
] as const;

type Cluster = "mainnet-beta" | "devnet" | "testnet";

type DecodedInstruction = {
  index: number;
  program_id: string;
  program_name: string;
  instruction_name: string;
  accounts: string[];
  args: Record<string, unknown>;
  raw_data: string | null;
};

type TxError = {
  kind: string;
  message: string;
  instruction_index: number | null;
  custom_code: number | null;
};

type AnalyzeResponse = {
  signature: string;
  cluster: string;
  status: "success" | "failed" | "unknown";
  slot: number | null;
  fee_lamports: number | null;
  compute_units: number | null;
  accounts: string[];
  instructions: DecodedInstruction[];
  logs: string[];
  errors: TxError[];
  ai: {
    flow: string;
    error_summary: string;
    fixes: string[];
    model: string;
    fallback_used: boolean;
  };
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

function shortKey(key: string, n = 4): string {
  if (key.length <= n * 2 + 3) return key;
  return `${key.slice(0, n)}…${key.slice(-n)}`;
}

export default function HomePage() {
  const [signature, setSignature] = useState("");
  const [cluster, setCluster] = useState<Cluster>("mainnet-beta");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!busy) {
      setStepIndex(0);
      return;
    }
    const id = window.setInterval(() => {
      setStepIndex((i) => (i + 1) % ANALYZE_STEPS.length);
    }, 2200);
    return () => window.clearInterval(id);
  }, [busy]);

  async function onAnalyze(e: FormEvent) {
    e.preventDefault();
    const sig = signature.trim();
    if (!sig) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signature: sig, cluster }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof body.detail === "string" ? body.detail : `Analyze failed (${res.status})`;
        throw new Error(detail);
      }
      setResult(body as AnalyzeResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-4 py-8 sm:px-6">
      <header className="elev flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-tosca-700">Developer tools</p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-ink sm:text-3xl">
            Solana Explorer AI
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Paste a transaction signature. Decode instructions, read logs, and get AI fix guidance.
          </p>
        </div>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted">
          Cluster
          <select
            className="select w-full sm:w-44"
            value={cluster}
            onChange={(e) => setCluster(e.target.value as Cluster)}
          >
            <option value="mainnet-beta">mainnet-beta</option>
            <option value="devnet">devnet</option>
            <option value="testnet">testnet</option>
          </select>
        </label>
      </header>

      <form onSubmit={onAnalyze} className="elev flex flex-col gap-3 p-5 sm:flex-row sm:items-end">
        <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-muted">
          Transaction signature
          <input
            className="field font-mono text-sm"
            placeholder="5VERv8… or base58 signature"
            value={signature}
            onChange={(e) => setSignature(e.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
        </label>
        <button type="submit" className="btn-primary shrink-0" disabled={busy || !signature.trim()}>
          {busy ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      {error && (
        <div
          className="elev border-l-4 p-4 text-sm"
          style={{ borderLeftColor: "var(--color-danger)" }}
          role="alert"
        >
          {error}
        </div>
      )}

      {busy && (
        <section
          className="elev flex flex-col items-center gap-4 p-10 text-center"
          role="status"
          aria-live="polite"
          aria-busy="true"
        >
          <div className="analyze-spinner" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-ink">Analyzing transaction…</p>
            <p className="analyze-step mt-2 text-sm text-muted">{ANALYZE_STEPS[stepIndex]}</p>
          </div>
        </section>
      )}

      {result && (
        <div className="flex flex-col gap-6">
          <section className="elev grid gap-4 p-5 sm:grid-cols-4">
            <Meta
              label="Status"
              value={result.status}
              tone={result.status === "success" ? "success" : result.status === "failed" ? "danger" : "muted"}
            />
            <Meta label="Slot" value={result.slot?.toLocaleString() ?? "—"} />
            <Meta
              label="Fee"
              value={result.fee_lamports != null ? `${result.fee_lamports.toLocaleString()} lamports` : "—"}
            />
            <Meta
              label="Compute"
              value={result.compute_units != null ? `${result.compute_units.toLocaleString()} CU` : "—"}
            />
          </section>

          <section className="elev p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold text-ink">AI explanation</h2>
              {result.ai.model && (
                <p className="text-xs font-medium text-tosca-700">
                  This response is using {result.ai.model}
                  {result.ai.fallback_used ? " (fallback)" : ""}.
                </p>
              )}
            </div>
            <p className="mt-3 text-sm leading-relaxed text-ink">{result.ai.flow}</p>
            <div
              className="mt-4 rounded-md border p-3 text-sm"
              style={{
                borderColor: "var(--border-subtle)",
                background: "var(--color-secondary)",
              }}
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">Errors</p>
              <p className="mt-1 text-ink">{result.ai.error_summary || "None reported."}</p>
            </div>
            {result.ai.fixes.length > 0 && (
              <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-ink">
                {result.ai.fixes.map((fix, i) => (
                  <li key={i}>{fix}</li>
                ))}
              </ul>
            )}
          </section>

          <section className="elev p-5">
            <h2 className="text-sm font-semibold text-ink">Instructions</h2>
            <ol className="mt-3 space-y-2">
              {result.instructions.map((ix) => (
                <li
                  key={`${ix.index}-${ix.program_id}-${ix.instruction_name}`}
                  className="rounded-md border px-3 py-3 text-sm"
                  style={{ borderColor: "var(--border-subtle)" }}
                >
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="nums text-xs font-medium text-tosca-700">#{ix.index}</span>
                    <span className="font-semibold">{ix.instruction_name}</span>
                    <span className="text-muted">{ix.program_name}</span>
                  </div>
                  <p className="mt-1 font-mono text-xs text-muted">{shortKey(ix.program_id, 6)}</p>
                  {Object.keys(ix.args).length > 0 && (
                    <pre className="mt-2 overflow-x-auto rounded bg-surface-secondary p-2 font-mono text-xs text-muted">
                      {JSON.stringify(ix.args, null, 2)}
                    </pre>
                  )}
                </li>
              ))}
              {result.instructions.length === 0 && (
                <li className="text-sm text-muted">No instructions decoded.</li>
              )}
            </ol>
          </section>

          {result.errors.length > 0 && (
            <section className="elev p-5">
              <h2 className="text-sm font-semibold text-ink">Parsed errors</h2>
              <ul className="mt-3 space-y-2">
                {result.errors.map((err, i) => (
                  <li key={i} className="text-sm" style={{ color: "var(--color-danger)" }}>
                    <span className="font-medium">[{err.kind}]</span> {err.message}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="elev p-5">
            <h2 className="text-sm font-semibold text-ink">Logs</h2>
            <pre className="mt-3 max-h-80 overflow-auto rounded-md bg-ink p-3 font-mono text-xs leading-relaxed text-surface-secondary">
              {result.logs.length ? result.logs.join("\n") : "No log messages."}
            </pre>
          </section>
        </div>
      )}

      {!result && !error && !busy && (
        <section className="elev p-8 text-center">
          <p className="text-sm text-muted">Enter a signature and click Analyze to start debugging.</p>
        </section>
      )}
    </div>
  );
}

function Meta({
  label,
  value,
  tone = "ink",
}: {
  label: string;
  value: string;
  tone?: "ink" | "success" | "danger" | "muted";
}) {
  const color =
    tone === "success"
      ? "var(--color-success)"
      : tone === "danger"
        ? "var(--color-danger)"
        : tone === "muted"
          ? "var(--color-muted)"
          : "var(--color-ink)";
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="nums mt-1 text-base font-semibold capitalize" style={{ color }}>
        {value}
      </p>
    </div>
  );
}
