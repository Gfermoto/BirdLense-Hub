import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from '../locales/en.json';
import ru from '../locales/ru.json';

const STORAGE_KEY = 'birdlense-lang';

export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'ru', label: 'Русский' },
] as const;

export type LanguageCode = (typeof LANGUAGES)[number]['code'];

const savedLang = (localStorage.getItem(STORAGE_KEY) as LanguageCode) || 'en';

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, ru: { translation: ru } },
  lng: savedLang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export function setLanguage(code: LanguageCode) {
  i18n.changeLanguage(code);
  localStorage.setItem(STORAGE_KEY, code);
}
