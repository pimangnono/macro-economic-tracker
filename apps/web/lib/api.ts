const API_BASE_URL =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000";

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

export type LiveBoardTrackItem = {
  trackId: string;
  trackName: string;
  mode: string;
  storyCount: number;
  topSummary?: SummaryFrame | null;
  stories: StoryPreview[];
};

export type LiveBoardResponse = {
  generatedAt: string;
  items: LiveBoardTrackItem[];
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

async function fetchJSON<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      next: { revalidate: 5 },
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export async function getLiveBoard(): Promise<LiveBoardResponse | null> {
  return fetchJSON<LiveBoardResponse>("/api/v1/tracks/live-board");
}

export async function getTrack(trackId: string): Promise<TrackStoriesResponse | null> {
  return fetchJSON<TrackStoriesResponse>(`/api/v1/tracks/${trackId}`);
}

export async function getStory(storyId: string): Promise<StoryDetailResponse | null> {
  return fetchJSON<StoryDetailResponse>(`/api/v1/stories/${storyId}`);
}

export async function getTrackBootstrap(): Promise<TrackBootstrapResponse | null> {
  return fetchJSON<TrackBootstrapResponse>("/api/v1/tracks/bootstrap");
}

export async function getSourceHealth(): Promise<SourceHealthResponse | null> {
  return fetchJSON<SourceHealthResponse>("/api/v1/ingestion/status");
}

export async function getRecentNotifications(): Promise<RecentNotificationsResponse | null> {
  return fetchJSON<RecentNotificationsResponse>("/api/v1/notifications/recent?limit=6");
}
