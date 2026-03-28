#!/usr/bin/env bash

set -euo pipefail

DATASET_ROOT="${VIDEO_DATASET_ROOT:-/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset}"
JOBS_ROOT="${VIDEO_JOBS_ROOT:-${DATASET_ROOT}/jobs}"
DEFAULT_JOBS=("000001" "000002" "000003")

if [ "$#" -gt 0 ]; then
  JOB_IDS=("$@")
else
  JOB_IDS=("${DEFAULT_JOBS[@]}")
fi

mkdir -p "${JOBS_ROOT}"

create_job() {
  local job_id="$1"
  local job_root="${JOBS_ROOT}/${job_id}"

  mkdir -p "${job_root}/source" "${job_root}/audio" "${job_root}/subtitles" "${job_root}/logs"

  if [ ! -f "${job_root}/job.json" ]; then
    cat > "${job_root}/job.json" <<EOF
{
  "job_id": "${job_id}",
  "job_schema_version": "2.0",
  "created_at": "",
  "updated_at": "",
  "voice": {},
  "paths": {
    "brief": "jobs/${job_id}/source/${job_id}_brief.json",
    "script": "jobs/${job_id}/source/${job_id}_script.json",
    "visual_manifest": "jobs/${job_id}/source/${job_id}_visual_manifest.json",
    "rendered_comfy_workflow": "jobs/${job_id}/source/${job_id}_rendered_comfy_workflow.json",
    "audio": "jobs/${job_id}/audio/${job_id}_narration.wav",
    "subtitles": "jobs/${job_id}/subtitles/${job_id}_narration.srt",
    "logs_dir": "jobs/${job_id}/logs"
  }
}
EOF
  fi

  if [ ! -f "${job_root}/status.json" ]; then
    cat > "${job_root}/status.json" <<EOF
{
  "brief_created": false,
  "script_generated": false,
  "audio_generated": false,
  "subtitles_generated": false,
  "visual_manifest_generated": false,
  "export_ready": false,
  "last_step": "created",
  "updated_at": "",
  "voice_id": "",
  "voice_scope": "",
  "voice_source": "",
  "voice_name": "",
  "voice_selection_mode": "",
  "voice_model_name": "",
  "voice_reference_file": "",
  "audio_file": "",
  "audio_generated_at": ""
}
EOF
  fi
}

for job_id in "${JOB_IDS[@]}"; do
  create_job "${job_id}"
done

echo "Estructura creada en: ${JOBS_ROOT}"
