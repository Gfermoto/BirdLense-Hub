export type BehaviorTagOption = {
  value: string;
  labelKey: string;
};

// Practical feeder-station vocabulary based on birdwatching references (eBird/Cornell/BTO).
export const BEHAVIOR_TAG_OPTIONS: BehaviorTagOption[] = [
  { value: 'feeding', labelKey: 'videoInfo.behaviorTags.feeding' },
  { value: 'food_handling', labelKey: 'videoInfo.behaviorTags.food_handling' },
  { value: 'drinking', labelKey: 'videoInfo.behaviorTags.drinking' },
  { value: 'bathing', labelKey: 'videoInfo.behaviorTags.bathing' },
  { value: 'self_maintenance', labelKey: 'videoInfo.behaviorTags.self_maintenance' },
  { value: 'resting', labelKey: 'videoInfo.behaviorTags.resting' },
  { value: 'vigilance', labelKey: 'videoInfo.behaviorTags.vigilance' },
  { value: 'agonistic', labelKey: 'videoInfo.behaviorTags.agonistic' },
  { value: 'alarm_or_flee', labelKey: 'videoInfo.behaviorTags.alarm_or_flee' },
  { value: 'transport_food', labelKey: 'videoInfo.behaviorTags.transport_food' },
  { value: 'parent_offspring', labelKey: 'videoInfo.behaviorTags.parent_offspring' },
  { value: 'pair_or_courtship', labelKey: 'videoInfo.behaviorTags.pair_or_courtship' },
];
