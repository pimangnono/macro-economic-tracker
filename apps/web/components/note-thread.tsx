"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

import { createNote, type CreateNotePayload, type NoteDetail } from "@/lib/api";

export function NoteThread({
  title,
  items,
  payload,
}: {
  title: string;
  items: NoteDetail[];
  payload: Omit<CreateNotePayload, "bodyMd">;
}) {
  const { data: session } = useSession();
  const router = useRouter();
  const [body, setBody] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session?.accessToken || !body.trim()) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    const response = await createNote(session.accessToken, {
      ...payload,
      bodyMd: body.trim(),
    });
    if (!response) {
      setError("Failed to save note");
      setIsSubmitting(false);
      return;
    }
    setBody("");
    setIsSubmitting(false);
    router.refresh();
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Notes</p>
          <h2>{title}</h2>
        </div>
      </div>
      <form className="inline-form" onSubmit={handleSubmit}>
        <textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Capture the desk view, handoff context, or evidence caveat."
          rows={4}
        />
        {error ? <p className="form-error">{error}</p> : null}
        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : "Add note"}
        </button>
      </form>
      <ul className="note-list">
        {items.length === 0 ? <li>No notes yet.</li> : null}
        {items.map((item) => (
          <li key={item.id}>
            <strong>{item.authorName ?? "Team note"}</strong>
            <p>{item.bodyMd}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
