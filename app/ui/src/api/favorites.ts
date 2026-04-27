import axios from 'axios';
import { BASE_API_URL } from './client';

export type FavoriteVideoSpecies = {
  id: number;
  name: string;
  image_url?: string | null;
  confidence: number;
  start_time: number;
  end_time: number;
  source: 'video' | 'audio' | string;
};

export type FavoriteVideo = {
  id: number;
  start_time: string;
  end_time: string;
  video_path: string;
  favorite: boolean;
  deleted: boolean;
  duration_seconds: number;
  species: FavoriteVideoSpecies[];
  scales?: {
    delta_kg: number;
    display_value: number;
    display_unit: 'kg' | 'g';
  } | null;
};

export type FavoriteSpeciesGroup = {
  species: {
    id: number;
    name: string;
    image_url?: string | null;
    parent_id?: number | null;
  };
  count: number;
  latest_start_time: string;
  videos: FavoriteVideo[];
};

export type FavoritesBySpeciesPayload = {
  total_videos: number;
  total_species: number;
  groups: FavoriteSpeciesGroup[];
  unclassified: {
    count: number;
    videos: FavoriteVideo[];
  };
};

export const fetchFavoritesBySpecies =
  async (): Promise<FavoritesBySpeciesPayload> => {
    const response = await axios.get(`${BASE_API_URL}/favorites/by-species`);
    return response.data;
  };
