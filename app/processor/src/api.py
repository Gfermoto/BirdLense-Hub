import logging
import os
import time

import requests


class API():
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Ensure the API URL base is available
        self.api_url_base = os.environ.get('API_URL_BASE')
        if not self.api_url_base:
            raise EnvironmentError(
                "API_URL_BASE environment variable is not set.")
        self._processor_secret = os.environ.get('PROCESSOR_SECRET', '').strip()

    def _headers(self):
        headers = {}
        if self._processor_secret:
            headers['X-Processor-Token'] = self._processor_secret
        return headers

    def _send_request(self, method, endpoint, json_data):
        """Helper function to send HTTP requests with timeout and retry on 5xx."""
        url = f"{self.api_url_base}/{endpoint}"
        timeout = 30
        max_retries = 3
        last_exc = None
        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method,
                    url,
                    json=json_data,
                    headers=self._headers(),
                    timeout=timeout,
                )
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                last_exc = e
                self.logger.warning(
                    f"API request failed for {url} (attempt {attempt + 1}/{max_retries}): {e}"
                )
                resp = getattr(e, "response", None)
                if resp is not None and 400 <= resp.status_code < 500:
                    break
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        self.logger.error(f"API request failed for {url}: {last_exc}")
        raise last_exc

    def notify_motion(self):
        # No need for try/except here since _send_request handles errors
        self._send_request('POST', 'notify/motion', {})

    def notify_species(
        self, species, image_path=None, image_base64=None, link=None, preview_source=None
    ):
        payload = {'detection': species}
        if image_base64:
            payload['image_base64'] = image_base64
        elif image_path:
            payload['image_path'] = image_path
        if link:
            payload['link'] = link
        if preview_source:
            payload['preview_source'] = preview_source
        self._send_request('POST', 'notify/detections', payload)

    def create_video(self, species_video, species_audio, start_time, end_time, video_path, spectrogram_path):
        # Fields to exclude from API payload (non-serializable or internal)
        exclude_fields = {'best_frame'}
        
        def clean_detection(d):
            return {k: v for k, v in d.items() if k not in exclude_fields}
        
        video_data = {
            'processor_version': '1',
            'species': [clean_detection(sp) for sp in species_video] + [
                {**sp, 'source': 'audio', 'detection_provider': 'birdnet_mqtt'}
                for sp in species_audio
            ],
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'video_path': video_path,
            'spectrogram_path': spectrogram_path
        }
        response = self._send_request('POST', 'videos', video_data)
        return response.json()

    def set_active_species(self, active_names):
        response = self._send_request('PUT', 'species/active', active_names)
        response_data = response.json()
        return response_data.get('active_feeder_names')

    def activity_log(self, type, data, id=None):
        log_data = {'type': type, 'data': data, 'id': id}
        response = self._send_request('POST', 'activity_log', log_data)
        response_data = response.json()
        # Capture the returned 'id' from the response
        return response_data.get('id')
