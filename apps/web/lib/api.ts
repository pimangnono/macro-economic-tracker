const API_BASE_URL =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000";

type FetchOptions = {
  token?: string;
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
};

export type SummaryFrame = {
  whatChanged?: string | null;
  whyItMatters?: string | null;
  whatToWatch?: string | null;
};

export type StoryPreview = {
  storyId: string;
  title: string;
  storyState: string;
  hotnessScore: number;
  confidenceScore: number;
  contradictionScore: number;
  latestEpisodeId?: string | null;
  latestEpisodeType?: string | null;
  headline?: string | null;
  whatChanged?: string | null;
  whyItMatters?: string | null;
  whatToWatch?: string | null;
  episodeCreatedAt?: string | null;
  priorityScore: number;
  relevanceScore: number;
};

export type TrackDetail = {
  trackId: string;
  name: string;
  slug: string;
  description?: string | null;
  mode: string;
  state: string;
  memoryWindowDays: number;
  alertPolicy: Record<string, unknown>;
  topSummary?: SummaryFrame | null;
  metrics: {
    storyCount: number;
    activeStoryCount: number;
    lastActivityAt?: string | null;
  };
};

export type TrackStoriesResponse = {
  generatedAt: string;
  track: TrackDetail;
  stories: StoryPreview[];
};

export type BootstrapOption = {
  id: string;
  label: string;
  value: string;
};

export type TrackBootstrapResponse = {
  workspaces: BootstrapOption[];
  modes: BootstrapOption[];
  states: BootstrapOption[];
};

export type CreateTrackPayload = {
  workspaceId: string;
  ownerUserId?: string | null;
  name: string;
  description?: string | null;
  mode: string;
  state: string;
  memoryWindowDays: number;
  alertPolicy: Record<string, unknown>;
  evidencePolicy: Record<string, unknown>;
};

export type EpisodeDetail = {
  episodeId: string;
  episodeType: string;
  headline: string;
  stateFrom?: string | null;
  stateTo?: string | null;
  summary: SummaryFrame;
  significanceScore: number;
  confidenceScore: number;
  contradictionScore: number;
  createdAt: string;
};

export type StoryDetailResponse = {
  generatedAt: string;
  story: {
    storyId: string;
    title: string;
    state: string;
    dominantMode: string;
    scores: Record<string, number>;
    summary: SummaryFrame;
    latestEpisode?: EpisodeDetail | null;
    episodes: EpisodeDetail[];
    sources: Array<{
      id: string;
      title: string;
      sourceName?: string | null;
      sourceType?: string | null;
      publishedAt?: string | null;
      documentType?: string | null;
    }>;
    evidence: Array<{
      id: string;
      quoteText: string;
      sourceName?: string | null;
      sourceType?: string | null;
      supportStatus?: string | null;
    }>;
  };
};

export type StoryContradictionItem = {
  sentenceId: string;
  sentenceText: string;
  verdict: string;
  evidenceSpanId: string;
  quoteText: string;
  sourceName?: string | null;
  supportStatus: string;
};

export type StoryContradictionsResponse = {
  generatedAt: string;
  items: StoryContradictionItem[];
};

export type SourceHealthItem = {
  sourceKey: string;
  displayName: string;
  sourceType: string;
  documentType: string;
  feedKind: string;
  feedUrl: string;
  status: string;
  isActive: boolean;
  lastRunStatus?: string | null;
  lastRunStartedAt?: string | null;
  lastRunFinishedAt?: string | null;
  lastSuccessAt?: string | null;
  lastPublishedAt?: string | null;
  discoveredCount: number;
  insertedCount: number;
  updatedCount: number;
  failedCount: number;
  errorText?: string | null;
};

export type SourceHealthResponse = {
  generatedAt: string;
  items: SourceHealthItem[];
};

export type RecentNotificationItem = {
  id: string;
  title: string;
  bodyText?: string | null;
  reason: string;
  channel: string;
  createdAt: string;
  scheduledFor?: string | null;
  sentAt?: string | null;
  readAt?: string | null;
  trackId?: string | null;
  trackName?: string | null;
  storyId?: string | null;
  storyTitle?: string | null;
  episodeId?: string | null;
  episodeHeadline?: string | null;
};

export type RecentNotificationsResponse = {
  generatedAt: string;
  items: RecentNotificationItem[];
};

export type CurrentUser = {
  id: string;
  email: string;
  displayName: string;
  timezone: string;
  isActive: boolean;
  defaultWorkspaceId?: string | null;
  workspaces: Array<{ id: string; name: string; slug: string; role: string }>;
};

export type InboxItem = {
  id: string;
  workspaceId: string;
  trackId?: string | null;
  trackName?: string | null;
  storyId?: string | null;
  storyTitle?: string | null;
  episodeId?: string | null;
  episodeHeadline?: string | null;
  mode?: string | null;
  state?: string | null;
  reason: string;
  priorityScore: number;
  confidenceScore: number;
  contradictionScore: number;
  createdAt: string;
  whatChanged?: string | null;
  whyItMatters?: string | null;
  whatToWatch?: string | null;
  sourceName?: string | null;
  isRead: boolean;
};

export type InboxResponse = {
  generatedAt: string;
  items: InboxItem[];
};

export type TrackListItem = {
  trackId: string;
  workspaceId: string;
  name: string;
  slug: string;
  mode: string;
  state: string;
  ownerName?: string | null;
  storyCount: number;
  activeStoryCount: number;
  unreadCount: number;
  lastActivityAt?: string | null;
};

export type TrackListResponse = {
  generatedAt: string;
  items: TrackListItem[];
};

export type NoteDetail = {
  id: string;
  workspaceId: string;
  authorUserId?: string | null;
  authorName?: string | null;
  scope: string;
  trackId?: string | null;
  storyId?: string | null;
  episodeId?: string | null;
  evidenceSpanId?: string | null;
  bodyMd: string;
  pinned: boolean;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
};

export type NotesResponse = {
  generatedAt: string;
  items: NoteDetail[];
};

export type CreateNotePayload = {
  scope: string;
  trackId?: string | null;
  storyId?: string | null;
  episodeId?: string | null;
  evidenceSpanId?: string | null;
  bodyMd: string;
  pinned?: boolean;
  metadata?: Record<string, unknown>;
};

export type SnapshotArtifact = {
  kind: string;
  url?: string | null;
  storageKey?: string | null;
  inlineText?: string | null;
  inlineJson?: Record<string, unknown> | null;
  contentType?: string | null;
  generated: boolean;
  status: string;
};

export type SnapshotDetail = {
  id: string;
  trackId: string;
  snapshotAt: string;
  summaryText?: string | null;
  summary?: SummaryFrame | null;
  metrics: Record<string, unknown>;
  artifactManifest: Record<string, SnapshotArtifact>;
  createdByAgent?: string | null;
  createdAt: string;
};

export type SnapshotsResponse = {
  generatedAt: string;
  items: SnapshotDetail[];
};

export type UpcomingEventItem = {
  id: string;
  title: string;
  publishedAt?: string | null;
  documentType?: string | null;
  sourceName?: string | null;
  canonicalUrl?: string | null;
};

export type UpcomingEventsResponse = {
  generatedAt: string;
  items: UpcomingEventItem[];
};

export type TrackCanvasResponse = {
  generatedAt: string;
  track: TrackDetail;
  stories: StoryPreview[];
  notes: NoteDetail[];
  snapshots: SnapshotDetail[];
  upcomingEvents: UpcomingEventItem[];
  modeData: {
    kind: string;
    blocks: Record<string, unknown>;
  };
};

export type WorkspaceMember = {
  userId: string;
  email: string;
  displayName: string;
  role: string;
  joinedAt: string;
  lastLoginAt?: string | null;
};

export type WorkspaceMembersResponse = {
  items: WorkspaceMember[];
};

export type WorkspaceInviteResponse = {
  invite: {
    id: string;
    workspaceId: string;
    email: string;
    role: string;
    inviteToken: string;
    expiresAt: string;
  };
};

async function fetchJSON<T>(path: string, options: FetchOptions = {}): Promise<T | null> {
  const headers = new Headers({
    Accept: "application/json",
  });
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export async function getCurrentUser(token: string): Promise<CurrentUser | null> {
  return fetchJSON<CurrentUser>("/api/v1/auth/me", { token });
}

export async function getInbox(token: string, workspaceId?: string): Promise<InboxResponse | null> {
  const query = workspaceId ? `?workspaceId=${workspaceId}` : "";
  return fetchJSON<InboxResponse>(`/api/v1/inbox${query}`, { token });
}

export async function getTracks(
  token: string,
  scope: "all" | "mine" | "team" = "all",
  workspaceId?: string,
): Promise<TrackListResponse | null> {
  const params = new URLSearchParams({ scope });
  if (workspaceId) {
    params.set("workspaceId", workspaceId);
  }
  return fetchJSON<TrackListResponse>(`/api/v1/tracks?${params.toString()}`, { token });
}

export async function getLiveBoard(
  token: string,
  workspaceId?: string,
): Promise<{ generatedAt: string; items: Array<Record<string, unknown>> } | null> {
  const query = workspaceId ? `?workspaceId=${workspaceId}` : "";
  return fetchJSON(`/api/v1/tracks/live-board${query}`, { token });
}

export async function getTrack(token: string, trackId: string): Promise<TrackStoriesResponse | null> {
  return fetchJSON<TrackStoriesResponse>(`/api/v1/tracks/${trackId}`, { token });
}

export async function getTrackCanvas(
  token: string,
  trackId: string,
): Promise<TrackCanvasResponse | null> {
  return fetchJSON<TrackCanvasResponse>(`/api/v1/tracks/${trackId}/canvas`, { token });
}

export async function getTrackBootstrap(
  token: string,
  workspaceId?: string,
): Promise<TrackBootstrapResponse | null> {
  const query = workspaceId ? `?workspaceId=${workspaceId}` : "";
  return fetchJSON<TrackBootstrapResponse>(`/api/v1/tracks/bootstrap${query}`, { token });
}

export async function createTrack(
  token: string,
  payload: CreateTrackPayload,
): Promise<TrackStoriesResponse | null> {
  return fetchJSON<TrackStoriesResponse>("/api/v1/tracks", {
    token,
    method: "POST",
    body: payload,
  });
}

export async function getStory(token: string, storyId: string): Promise<StoryDetailResponse | null> {
  return fetchJSON<StoryDetailResponse>(`/api/v1/stories/${storyId}`, { token });
}

export async function getStoryContradictions(
  token: string,
  storyId: string,
): Promise<StoryContradictionsResponse | null> {
  return fetchJSON<StoryContradictionsResponse>(`/api/v1/stories/${storyId}/contradictions`, {
    token,
  });
}

export async function getSourceHealth(token: string): Promise<SourceHealthResponse | null> {
  return fetchJSON<SourceHealthResponse>("/api/v1/ingestion/status", { token });
}

export async function getRecentNotifications(
  token: string,
  workspaceId?: string,
): Promise<RecentNotificationsResponse | null> {
  const params = new URLSearchParams({ limit: "20" });
  if (workspaceId) {
    params.set("workspaceId", workspaceId);
  }
  return fetchJSON<RecentNotificationsResponse>(`/api/v1/notifications/recent?${params.toString()}`, {
    token,
  });
}

export async function markNotificationRead(token: string, notificationId: string) {
  return fetchJSON<{ status: string }>(`/api/v1/notifications/${notificationId}/read`, {
    token,
    method: "POST",
  });
}

export async function muteNotification(token: string, notificationId: string) {
  return fetchJSON<{ status: string }>(`/api/v1/notifications/${notificationId}/mute`, {
    token,
    method: "POST",
  });
}

export async function getNotes(
  token: string,
  params: Record<string, string>,
): Promise<NotesResponse | null> {
  const query = new URLSearchParams(params).toString();
  return fetchJSON<NotesResponse>(`/api/v1/notes?${query}`, { token });
}

export async function createNote(
  token: string,
  payload: CreateNotePayload,
): Promise<{ note: NoteDetail } | null> {
  return fetchJSON<{ note: NoteDetail }>("/api/v1/notes", {
    token,
    method: "POST",
    body: payload,
  });
}

export async function createSnapshot(
  token: string,
  trackId: string,
  focus?: string,
): Promise<{ snapshot: SnapshotDetail } | null> {
  return fetchJSON<{ snapshot: SnapshotDetail }>(`/api/v1/tracks/${trackId}/snapshots`, {
    token,
    method: "POST",
    body: { focus },
  });
}

export async function getSnapshots(
  token: string,
  trackId: string,
): Promise<SnapshotsResponse | null> {
  return fetchJSON<SnapshotsResponse>(`/api/v1/tracks/${trackId}/snapshots`, { token });
}

export async function getUpcomingEvents(
  token: string,
  trackId: string,
): Promise<UpcomingEventsResponse | null> {
  return fetchJSON<UpcomingEventsResponse>(`/api/v1/tracks/${trackId}/upcoming-events`, { token });
}

export async function getWorkspaceMembers(
  token: string,
  workspaceId: string,
): Promise<WorkspaceMembersResponse | null> {
  return fetchJSON<WorkspaceMembersResponse>(`/api/v1/workspaces/${workspaceId}/members`, { token });
}

export async function inviteWorkspaceMember(
  token: string,
  workspaceId: string,
  email: string,
  role: string,
): Promise<WorkspaceInviteResponse | null> {
  return fetchJSON<WorkspaceInviteResponse>(`/api/v1/workspaces/${workspaceId}/members/invite`, {
    token,
    method: "POST",
    body: { email, role },
  });
}

export async function updateWorkspaceMemberRole(
  token: string,
  workspaceId: string,
  userId: string,
  role: string,
): Promise<WorkspaceMembersResponse | null> {
  return fetchJSON<WorkspaceMembersResponse>(`/api/v1/workspaces/${workspaceId}/members/${userId}`, {
    token,
    method: "PATCH",
    body: { role },
  });
}
