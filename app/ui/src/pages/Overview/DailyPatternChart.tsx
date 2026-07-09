import React from 'react';
import { useTheme } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import useMediaQuery from '@mui/material/useMediaQuery';
import { OverviewTopSpecies } from '../../types';
import { labelToUniqueHexColor } from '../../util';
import { useTranslation } from 'react-i18next';
import { overviewSpeciesLabel } from './overviewSpeciesLabel';
import { Dayjs } from 'dayjs';

const polarToCartesian = (
  centerX: number,
  centerY: number,
  radius: number,
  angleInDegrees: number,
) => {
  // Rotate 180 degrees to put noon at top
  const angleInRadians = ((angleInDegrees + 90) * Math.PI) / 180.0;
  return {
    x: centerX + radius * Math.cos(angleInRadians),
    y: centerY + radius * Math.sin(angleInRadians),
  };
};

const describeArc = (
  x: number,
  y: number,
  radius: number,
  startAngle: number,
  endAngle: number,
) => {
  const start = polarToCartesian(x, y, radius, endAngle);
  const end = polarToCartesian(x, y, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';
  return [
    'M',
    start.x,
    start.y,
    'A',
    radius,
    radius,
    0,
    largeArcFlag,
    0,
    end.x,
    end.y,
  ].join(' ');
};

interface DailyPatternChartProps {
  data: OverviewTopSpecies[];
  date: Dayjs;
  size?: number;
  observerTimezone?: string;
}

export const DailyPatternChart: React.FC<DailyPatternChartProps> = ({
  data,
  date,
  size: propSize,
  observerTimezone,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigate = useNavigate();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // Adjust size based on screen size
  const size = isMobile
    ? Math.min(window.innerWidth * 0.8, 400)
    : (propSize ?? 600);
  const center = size / 2;

  const maxDetections = Math.max(
    ...data.flatMap((d) =>
      Array.from({ length: 24 }, (_, i) => d.detections[i] || 0),
    ),
  );

  const hours = Array.from({ length: 24 }, (_, i) => i);
  const hourRadius = size * 0.42;
  const hourMarks = hours.map((hour) => {
    const angle = (hour * 360) / 24;
    const pos = polarToCartesian(center, center, hourRadius, angle);
    return { hour, pos };
  });

  const ringWidth = (size * 0.35) / (data.length + 1);

  const handleArcClick = (speciesId: number, hour: number) => {
    navigate(
      `/timeline?speciesId=${speciesId}&date=${date.format('YYYY-MM-DD')}&hour=${hour}`,
    );
  };

  return (
    <Box
      sx={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
      }}
    >
      <Box
        sx={{
          width: size,
          height: size,
          position: 'relative',
          margin: 'auto',
        }}
      >
        <svg width={size} height={size}>
          {/* Background circle */}
          <circle
            cx={center}
            cy={center}
            r={size * 0.45}
            fill="none"
            stroke={theme.palette.grey[200]}
            strokeWidth="1"
          />

          {/* Hour marks */}
          {hourMarks.map(({ hour, pos }) => (
            <g key={hour}>
              <line
                x1={center}
                y1={center}
                x2={pos.x}
                y2={pos.y}
                stroke={theme.palette.grey[300]}
                strokeWidth="1"
                opacity="0.5"
              />
              <text
                x={pos.x}
                y={pos.y}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={isMobile ? '10' : '12'}
                fill={theme.palette.text.secondary}
                transform={`
                  rotate(${(hour * 360) / 24},${pos.x},${pos.y})
                  ${hour >= 6 && hour <= 18 ? 'rotate(180,' + pos.x + ',' + pos.y + ')' : ''}
                `}
              >
                {`${String(hour).padStart(2, '0')}:00`}
              </text>
            </g>
          ))}

          {/* Species activity rings */}
          {data.map((species, index) => {
            const radius = size * 0.15 + index * ringWidth;
            const color = labelToUniqueHexColor(species.name);

            return hours.map((hour) => {
              const startAngle = (hour * 360) / 24;
              const endAngle = ((hour + 1) * 360) / 24;
              const detections = species.detections[hour] || 0;
              const intensity =
                detections === 0
                  ? 0
                  : 0.25 + (0.7 * detections) / maxDetections; // Scale non-zero values from 0.25 to 1.0

              return (
                <Tooltip
                  key={`${species.name}-${hour}`}
                  title={
                    <Typography>
                      {species.name}: {detections} detections at {hour}:00
                    </Typography>
                  }
                  slotProps={{
                    popper: {
                      sx: { pointerEvents: 'none' },
                    },
                  }}
                >
                  <path
                    d={describeArc(
                      center,
                      center,
                      radius,
                      startAngle,
                      endAngle,
                    )}
                    fill="none"
                    stroke={color}
                    strokeWidth={ringWidth * 0.8}
                    opacity={Math.max(intensity, 0.05)}
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleArcClick(species.id, hour)}
                  />
                </Tooltip>
              );
            });
          })}

          {/* Current time indicator */}
          {(() => {
            const now = new Date();
            const formatter = new Intl.DateTimeFormat('en-GB', {
              hour: '2-digit',
              minute: '2-digit',
              hour12: false,
              ...(observerTimezone ? { timeZone: observerTimezone } : {}),
            });
            const parts = formatter.formatToParts(now);
            const hoursPart = Number(
              parts.find((p) => p.type === 'hour')?.value ?? '0',
            );
            const minutesPart = Number(
              parts.find((p) => p.type === 'minute')?.value ?? '0',
            );
            const currentAngle =
              ((hoursPart * 60 + minutesPart) * 360) / (24 * 60);
            const pos = polarToCartesian(
              center,
              center,
              size * 0.45,
              currentAngle,
            );

            return (
              <line
                x1={center}
                y1={center}
                x2={pos.x}
                y2={pos.y}
                stroke={theme.palette.error.main}
                strokeWidth="2"
              />
            );
          })()}
        </svg>
      </Box>

      {/* Legend */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: 2,
          p: 1,
        }}
      >
        {data.map((species) => {
          const totalDetections = species.detections.reduce((a, b) => a + b, 0);
          return (
            <Box
              key={species.name}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
              }}
            >
              <Box
                sx={{
                  width: 16,
                  height: 16,
                  backgroundColor: labelToUniqueHexColor(species.name),
                }}
              />
              <Typography variant="caption">
                {overviewSpeciesLabel(t, species)} ({totalDetections})
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};

export default DailyPatternChart;
