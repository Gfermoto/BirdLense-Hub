import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CamerasListField } from './CamerasListField';

describe('CamerasListField', () => {
  it('uses Go2RTC stream name as camera id and preserves slot', () => {
    const onChange = vi.fn();
    render(
      <CamerasListField
        value={[
          {
            id: 'legacy-id',
            camera_slot: 'camera_2',
            stream_name: 'BirdBox',
            detect_stream_name: 'BirdBox_detect',
            name: 'Feeder',
          },
        ]}
        onChange={onChange}
      />,
    );

    expect(screen.queryByLabelText('camera_id')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Recording stream name'), {
      target: { value: 'Forest' },
    });

    expect(onChange).toHaveBeenLastCalledWith([
      {
        id: 'Forest',
        camera_slot: 'camera_2',
        stream_name: 'Forest',
        name: 'Feeder',
        detect_stream_name: 'BirdBox_detect',
      },
    ]);
  });

  it('warns when detection stream equals recording stream', () => {
    render(
      <CamerasListField
        value={[
          {
            stream_name: 'BirdBox',
            detect_stream_name: 'BirdBox',
            name: 'Feeder',
          },
        ]}
        onChange={vi.fn()}
      />,
    );

    expect(
      screen.getByText(
        'Detection stream must be a separate lores stream, not the recording stream.',
      ),
    ).toBeInTheDocument();
  });
});
