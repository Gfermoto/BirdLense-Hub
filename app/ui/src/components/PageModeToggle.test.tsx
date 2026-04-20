import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { PageModeToggle } from './PageModeToggle';

describe('PageModeToggle', () => {
  it('calls onChange when switching to another mode', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<PageModeToggle value="simple" onChange={onChange} />);

    await user.click(screen.getByRole('button', { name: /advanced/i }));

    expect(onChange).toHaveBeenCalledWith('advanced');
  });

  it('does not fire when clicking the already selected mode', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<PageModeToggle value="advanced" onChange={onChange} />);

    await user.click(screen.getByRole('button', { name: /advanced/i }));

    expect(onChange).not.toHaveBeenCalled();
  });

  it('renders custom labels when provided', () => {
    render(
      <PageModeToggle
        value="simple"
        onChange={vi.fn()}
        simpleLabel="Overview"
        advancedLabel="Admin tools"
      />,
    );

    expect(
      screen.getByRole('button', { name: 'Overview' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Admin tools' }),
    ).toBeInTheDocument();
  });
});
