"use client";

import { FormEvent, startTransition, useState } from "react";
import { useRouter } from "next/navigation";

import { CreateTrackPayload, TrackBootstrapResponse } from "@/lib/api";

const PUBLIC_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type TrackCreateFormProps = {
  bootstrap: TrackBootstrapResponse;
};

export function TrackCreateForm({ bootstrap }: TrackCreateFormProps) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [workspaceId, setWorkspaceId] = useState(bootstrap.workspaces[0]?.id ?? "");
  const [mode, setMode] = useState(bootstrap.modes[0]?.value ?? "scheduled_release");
  const [state, setState] = useState("active");
  const [memoryWindowDays, setMemoryWindowDays] = useState(30);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const payload: CreateTrackPayload = {
      workspaceId,
      name,
      description: description || null,
      mode,
      state,
      memoryWindowDays,
      alertPolicy: {
        delivery: "in_app",
        cadence: state === "active" ? "immediate" : "digest",
        threshold: "state_change",
      },
      evidencePolicy: {
        strict: true,
      },
    };

    try {
      const response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1/tracks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Track creation failed");
      }

      const json = (await response.json()) as { track: { trackId: string } };
      startTransition(() => {
        router.push(`/tracks/${json.track.trackId}`);
        router.refresh();
      });
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Track creation failed. Check that the API is reachable.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="create-form" onSubmit={handleSubmit}>
      <div className="create-form__grid">
        <label>
          <span>Track name</span>
          <input
            name="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="US inflation"
            minLength={3}
            required
          />
        </label>

        <label>
          <span>Workspace</span>
          <select
            name="workspaceId"
            value={workspaceId}
            onChange={(event) => setWorkspaceId(event.target.value)}
            required
          >
            {bootstrap.workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Mode</span>
          <select name="mode" value={mode} onChange={(event) => setMode(event.target.value)}>
            {bootstrap.modes.map((item) => (
              <option key={item.id} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>State</span>
          <select name="state" value={state} onChange={(event) => setState(event.target.value)}>
            {bootstrap.states.map((item) => (
              <option key={item.id} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Memory window (days)</span>
          <input
            name="memoryWindowDays"
            type="number"
            min={7}
            max={365}
            value={memoryWindowDays}
            onChange={(event) => setMemoryWindowDays(Number(event.target.value))}
          />
        </label>

        <label className="create-form__full">
          <span>Description</span>
          <textarea
            name="description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What should this track monitor, and why?"
            rows={5}
          />
        </label>
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <div className="create-form__actions">
        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Creating..." : "Create track"}
        </button>
      </div>
    </form>
  );
}

