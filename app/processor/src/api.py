import logging
import os
import threading
import time

import requests
from processor_runtime_stats import inc_counter, observe_timing
from processor_provenance import resolve_processor_version


class API:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Ensure the API URL base is available
        self.api_url_base = os.environ.get("API_URL_BASE")
        if not self.api_url_base:
            raise EnvironmentError("API_URL_BASE environment variable is not set.")
        self._processor_secret = os.environ.get("PROCESSOR_SECRET", "").strip()

    def _headers(self):
        headers = {}
        if self._processor_secret:
            headers["X-Processor-Token"] = self._processor_secret
        return headers

    def _send_request(self, method, endpoint, json_data, *, timeout=30, max_retries=3):
        """Helper function to send HTTP requests with timeout and retry on 5xx."""
        url = f"{self.api_url_base}/{endpoint}"
        last_exc = None
        for attempt in range(max_retries):
            st = time.time()
            try:
                response = requests.request(
                    method,
                    url,
                    json=json_data,
                    headers=self._headers(),
                    timeout=timeout,
                )
                response.raise_for_status()
                observe_timing("api_request", (time.time() - st) * 1000.0)
                if attempt > 0:
                    inc_counter("api_request_retries_total", attempt)
                return response
            except requests.exceptions.RequestException as e:
                observe_timing("api_request", (time.time() - st) * 1000.0)
                last_exc = e
                self.logger.warning(f"API request failed for {url} (attempt {attempt + 1}/{max_retries}): {e}")
                resp = getattr(e, "response", None)
                if resp is not None and 400 <= resp.status_code < 500:
                    inc_counter("api_request_client_errors_total")
                    if int(resp.status_code) == 409 and endpoint == "videos":
                        inc_counter("api_ingest_conflict_total")
                        try:
                            body = resp.json() if callable(getattr(resp, "json", None)) else {}
                        except ValueError:
                            body = {}
                        reason = str((body or {}).get("conflict_reason") or "unknown").strip().lower()
                        if reason:
                            inc_counter(f"api_ingest_conflict_reason_{reason}_total")
                    break
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
        inc_counter("api_request_failures_total")
        self.logger.error(f"API request failed for {url}: {last_exc}")
        raise last_exc

    def notify_motion(self):
        # No need for try/except here since _send_request handles errors
        self._send_request("POST", "notify/motion", {})

    def notify_species(
        self,
        species,
        image_path=None,
        image_base64=None,
        link=None,
        preview_source=None,
        notification_eligible=True,
        suppress_reason=None,
    ):
        payload = {"detection": species}
        if image_base64:
            payload["image_base64"] = image_base64
        elif image_path:
            payload["image_path"] = image_path
        if link:
            payload["link"] = link
        if preview_source:
            payload["preview_source"] = preview_source
        payload["notification_eligible"] = bool(notification_eligible)
        if suppress_reason:
            payload["suppress_reason"] = suppress_reason
        self._send_request("POST", "notify/detections", payload)

    def create_video(
        self,
        species_video,
        species_audio,
        start_time,
        end_time,
        video_path,
        trigger_source=None,
        scales_weight_delta_kg=None,
        camera_id=None,
    ):
        # Fields to exclude from API payload (non-serializable or internal)
        exclude_fields = {"best_frame"}
        processor_version, _version_source = resolve_processor_version()

        def clean_detection(d):
            return {k: v for k, v in d.items() if k not in exclude_fields}

        video_data = {
            "processor_version": processor_version,
            "species": [clean_detection(sp) for sp in species_video]
            + [{**sp, "source": "audio", "detection_provider": "birdnet_mqtt"} for sp in species_audio],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "video_path": video_path,
        }
        if trigger_source is not None and str(trigger_source).strip():
            video_data["trigger_source"] = str(trigger_source).strip().lower()
        if camera_id is not None and str(camera_id).strip():
            video_data["camera_id"] = str(camera_id).strip()[:64]
        if scales_weight_delta_kg is not None:
            video_data["scales_weight_delta_kg"] = float(scales_weight_delta_kg)
        response = self._send_request(
            "POST",
            "videos",
            video_data,
            timeout=90,
            max_retries=1,
        )
        return response.json()

    def set_active_species(self, active_names):
        response = self._send_request("PUT", "species/active", active_names)
        response_data = response.json()
        return response_data.get("active_feeder_names")

    def activity_log(self, type, data, id=None):
        log_data = {"type": type, "data": data, "id": id}
        timeout = 30 if type == "heartbeat" else 5
        max_retries = 2 if type == "heartbeat" else 1
        response = self._send_request(
            "POST",
            "activity_log",
            log_data,
            timeout=timeout,
            max_retries=max_retries,
        )
        response_data = response.json()
        # Capture the returned 'id' from the response
        return response_data.get("id")

    def activity_log_async(self, type, data, id=None):
        """Non-blocking activity_log for finalize tail (#597)."""

        def _run() -> None:
            try:
                self.activity_log(type, data, id=id)
            except Exception:
                self.logger.debug("async activity_log failed type=%s", type, exc_info=True)

        threading.Thread(
            target=_run,
            daemon=True,
            name=f"birdlense-activity-log-{type}",
        ).start()
