import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RecognitionImprovementCard } from './RecognitionImprovementCard';

const fetchRecognitionImprovementSummary = vi.hoisted(() =>
  vi.fn().mockResolvedValue({
    active_mode: 'heuristic',
    settings: { enabled: true, alpha: 0.6 },
    feedback: {
      corrected_examples: 4,
      unique_videos: 3,
      unique_species: 3,
      ready_for_training: false,
      examples_until_ready: 6,
      thresholds: {
        corrected_examples: 10,
        unique_videos: 5,
        unique_species: 3,
      },
      latest_feedback_at: '2026-04-21T00:00:00Z',
    },
    model: {
      label: 'Built-in heuristic',
      active_model_id: null,
      configured_path: '',
      trained_model_count: 0,
      last_trained_at: null,
      can_roll_back: false,
    },
  }),
);
const startRecognitionImprovementTrain = vi.hoisted(() =>
  vi.fn().mockResolvedValue({ message: 'started' }),
);
const fetchRecognitionImprovementTrainStatus = vi.hoisted(() =>
  vi.fn().mockResolvedValue({ status: 'idle' }),
);
const rollbackRecognitionImprovement = vi.hoisted(() =>
  vi.fn().mockResolvedValue({ active_mode: 'heuristic' }),
);

vi.mock('../../api/speciesRegistryHub', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('../../api/speciesRegistryHub')>();
  return {
    ...actual,
    fetchRecognitionImprovementSummary,
    startRecognitionImprovementTrain,
    fetchRecognitionImprovementTrainStatus,
    rollbackRecognitionImprovement,
  };
});

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <RecognitionImprovementCard />
    </QueryClientProvider>,
  );
}

describe('RecognitionImprovementCard', () => {
  beforeEach(() => {
    fetchRecognitionImprovementSummary.mockClear();
    startRecognitionImprovementTrain.mockClear();
    fetchRecognitionImprovementTrainStatus.mockClear();
    rollbackRecognitionImprovement.mockClear();
    fetchRecognitionImprovementSummary.mockResolvedValue({
      active_mode: 'heuristic',
      settings: { enabled: true, alpha: 0.6 },
      feedback: {
        corrected_examples: 4,
        unique_videos: 3,
        unique_species: 3,
        ready_for_training: false,
        examples_until_ready: 6,
        thresholds: {
          corrected_examples: 10,
          unique_videos: 5,
          unique_species: 3,
        },
        latest_feedback_at: '2026-04-21T00:00:00Z',
      },
      model: {
        label: 'Built-in heuristic',
        active_model_id: null,
        configured_path: '',
        trained_model_count: 0,
        last_trained_at: null,
        can_roll_back: false,
      },
    });
  });

  it('shows user-facing readiness and active mode', async () => {
    renderCard();

    expect(await screen.findAllByText(/built-in heuristic/i)).toHaveLength(2);
    expect(screen.getByText(/4 examples/i)).toBeInTheDocument();
    expect(
      screen.getByText(/need 6 more corrected examples/i),
    ).toBeInTheDocument();
  });

  it('starts training from the primary action', async () => {
    const user = userEvent.setup();
    fetchRecognitionImprovementSummary.mockResolvedValueOnce({
      active_mode: 'heuristic',
      settings: { enabled: true, alpha: 0.6 },
      feedback: {
        corrected_examples: 12,
        unique_videos: 6,
        unique_species: 4,
        ready_for_training: true,
        examples_until_ready: 0,
        thresholds: {
          corrected_examples: 10,
          unique_videos: 5,
          unique_species: 3,
        },
        latest_feedback_at: '2026-04-21T00:00:00Z',
      },
      model: {
        label: 'Built-in heuristic',
        active_model_id: null,
        configured_path: '',
        trained_model_count: 0,
        last_trained_at: null,
        can_roll_back: false,
      },
    });
    renderCard();

    await user.click(
      await screen.findByRole('button', { name: /update model/i }),
    );

    await waitFor(() => {
      expect(startRecognitionImprovementTrain).toHaveBeenCalledTimes(1);
    });
  });
});
