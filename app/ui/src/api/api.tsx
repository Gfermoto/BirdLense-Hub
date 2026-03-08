import { Dayjs } from 'dayjs';
import {
  mockBirdDirectory,
  mockBirdFood,
  mockTimeline,
  mockOverviewData,
  mockSetttings,
  mockSpeciesSummary,
  mockVideo,
  mockWeather,
} from './mocks';
import {
  BirdFood,
  SpeciesVisit,
  Settings,
  SpeciesSummary,
  OverviewData,
  Species,
} from '../types';
import axios from 'axios';

const useMockData = false; // Set to false to use real API calls
// Relative path = same origin (works with any host/IP)
export const BASE_URL = typeof window !== 'undefined' ? '' : 'http://birdlense.local';
export const BASE_API_URL = `${BASE_URL}/api/ui`;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const fetchTimeline = async (
  startTime: Dayjs,
  endTime: Dayjs,
): Promise<SpeciesVisit[]> => {
  if (useMockData) {
    await sleep(1000);
    return mockTimeline;
  } else {
    const response = await axios.get(`${BASE_API_URL}/timeline`, {
      params: {
        start_time: startTime.unix(),
        end_time: endTime.unix(),
      },
    });
    return response.data;
  }
};

export const fetchWeather = async () => {
  if (useMockData) {
    await sleep(1000);
    return mockWeather;
  } else {
    const response = await axios.get(`${BASE_API_URL}/weather`);
    return response.data;
  }
};

export const fetchVideo = async (id: string) => {
  if (useMockData) {
    await sleep(1000);
    return mockVideo;
  } else {
    const response = await axios.get(`${BASE_API_URL}/videos/${id}`);
    return response.data;
  }
};

export const fetchBirdFood = async (): Promise<BirdFood[]> => {
  if (useMockData) {
    await sleep(1000);
    return mockBirdFood;
  } else {
    const response = await axios.get(`${BASE_API_URL}/birdfood`);
    return response.data;
  }
};

export const toggleBirdFood = async (id: number) => {
  if (useMockData) {
    await sleep(1000);
    const food = mockBirdFood.find((item) => item.id === id);
    if (food) food.active = !food.active;
    return food;
  } else {
    const response = await axios.patch(`${BASE_API_URL}/birdfood/${id}/toggle`);
    return response.data;
  }
};

export const addBirdFood = async (newFood: Partial<BirdFood>) => {
  if (useMockData) {
    await sleep(1000);
    mockBirdFood.unshift({ id: 10, active: true, ...newFood } as BirdFood);
    return newFood;
  } else {
    const response = await axios.post(`${BASE_API_URL}/birdfood`, newFood);
    return response.data;
  }
};

export const fetchCameras = async (): Promise<
  { id: string; name: string; stream_url: string; feeder?: string }[]
> => {
  if (useMockData) {
    await sleep(200);
    return [{ id: 'bird_cam', name: 'Bird Cam', stream_url: '/processor/live' }];
  }
  const response = await axios.get(`${BASE_API_URL}/cameras`);
  return response.data.cameras || [];
};

export const fetchStatus = async (): Promise<{
  web: string;
  processor: string;
  video: string;
  mqtt: string;
  esphome?: string;
  yolo: string;
}> => {
  if (useMockData) {
    await sleep(300);
    return { web: 'ok', processor: 'ok', video: 'ok', mqtt: 'unknown', esphome: 'not_used', yolo: 'ok' };
  }
  const response = await axios.get(`${BASE_API_URL}/status`);
  return response.data;
};

export const dispenseFeed = async (): Promise<{ success: boolean; message?: string }> => {
  if (useMockData) {
    await sleep(500);
    return { success: true, message: 'Feed dispensed' };
  }
  try {
    const response = await axios.post(`${BASE_API_URL}/feed/dispense`);
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed to dispense feed',
    };
  }
};

export const fetchSettings = async () => {
  if (useMockData) {
    await sleep(1000);
    return mockSetttings;
  } else {
    const response = await axios.get(`${BASE_API_URL}/settings`);
    return response.data;
  }
};

export const updateSettings = async (settings: Settings) => {
  if (useMockData) {
    await sleep(1000);
    return settings;
  } else {
    const response = await axios.patch(`${BASE_API_URL}/settings`, settings);
    return response.data;
  }
};

export const restartProcessor = async (): Promise<{ success: boolean; message?: string }> => {
  if (useMockData) {
    await sleep(500);
    return { success: true, message: 'Restart requested' };
  }
  try {
    const response = await axios.post(`${BASE_API_URL}/restart-processor`);
    return { success: true, message: response.data?.message };
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } };
    return {
      success: false,
      message: err.response?.data?.error || 'Failed to restart',
    };
  }
};

export const fetchCoordinatesByZip = async (
  zip: string,
): Promise<{ lat: string; lon: string }> => {
  if (useMockData) {
    await sleep(1000);
    return { lat: '40.7128', lon: '-74.0060' }; // Mock coordinates
  } else {
    const response = await axios.get(
      'https://nominatim.openstreetmap.org/search',
      {
        params: {
          format: 'json',
          postalcode: zip,
          countrycodes: 'ru,us,de,gb',
        },
      },
    );
    const data = response.data;

    if (data && data.length > 0) {
      return {
        lat: data[0].lat,
        lon: data[0].lon,
      };
    } else {
      throw new Error('Invalid ZIP code or no data found.');
    }
  }
};

export const fetchBirdDirectory = async (): Promise<Species[]> => {
  if (useMockData) {
    await sleep(1000);
    return mockBirdDirectory;
  } else {
    const response = await axios.get(`${BASE_API_URL}/species`);
    return response.data;
  }
};

export const fetchOverviewData = async (
  date: string,
): Promise<OverviewData> => {
  if (useMockData) {
    await sleep(1000);
    return mockOverviewData;
  } else {
    // Create local day boundaries and convert to UTC timestamps
    const localStart = new Date(date + 'T00:00:00');
    const localEnd = new Date(date + 'T23:59:59.999');
    const response = await axios.get(`${BASE_API_URL}/overview`, {
      params: {
        start_time: Math.floor(localStart.getTime() / 1000),
        end_time: Math.floor(localEnd.getTime() / 1000),
      },
    });
    return response.data;
  }
};

export const fetchSpeciesSummary = async (
  speciesId: number,
): Promise<SpeciesSummary> => {
  if (useMockData) {
    await sleep(1000);
    return mockSpeciesSummary;
  } else {
    const response = await axios.get(
      `${BASE_API_URL}/species/${speciesId}/summary`,
    );
    return response.data;
  }
};

export const fetchDailySummary = async (
  date: string,
): Promise<{ summary: string }> => {
  if (useMockData) {
    await sleep(2000);
    return {
      summary:
        'This is a mock summary for ' + date + '. The birds were active today!',
    };
  } else {
    try {
      // Create local day boundaries and convert to UTC timestamps
      const localStart = new Date(date + 'T00:00:00');
      const localEnd = new Date(date + 'T23:59:59.999');
      const response = await axios.post(`${BASE_API_URL}/summary`, {
        start_time: Math.floor(localStart.getTime() / 1000),
        end_time: Math.floor(localEnd.getTime() / 1000),
      });
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.data?.error) {
        throw new Error(error.response.data.error);
      }
      throw error;
    }
  }
};
