import type { TFunction } from 'i18next';

/** Map known English backend warnings to i18n; unknown strings pass through. */
export function localizedConfigAuditWarning(w: string, t: TFunction): string {
  const diff =
    /^motion\.opencv_diff_threshold=(\d+) is above the hub default \((\d+)\)/.exec(
      w,
    );
  if (diff) {
    return t('system.configAuditWarnOpencvDiff', {
      current: diff[1],
      recommended: diff[2],
    });
  }
  const area =
    /^motion\.opencv_min_contour_area=(\d+) is above the hub default \((\d+)\)/.exec(
      w,
    );
  if (area) {
    return t('system.configAuditWarnOpencvContour', {
      current: area[1],
      recommended: area[2],
    });
  }
  return w;
}
