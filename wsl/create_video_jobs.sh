#!/usr/bin/env bash

# wsl\create_video_jobs.sh
set -euo pipefail

DATASET_ROOT="/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset"
JOBS_ROOT="${DATASET_ROOT}/jobs"

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

  echo "Creando job: ${job_id}"

  mkdir -p "${job_root}/source"
  mkdir -p "${job_root}/audio"
  mkdir -p "${job_root}/subtitles"
  mkdir -p "${job_root}/images/previews"
  mkdir -p "${job_root}/videos/previews"
  mkdir -p "${job_root}/timeline/vertical"
  mkdir -p "${job_root}/timeline/horizontal"
  mkdir -p "${job_root}/output/vertical"
  mkdir -p "${job_root}/output/horizontal"
  mkdir -p "${job_root}/logs"
  mkdir -p "${job_root}/tmp/comfy"
  mkdir -p "${job_root}/tmp/render"

  if [ ! -f "${job_root}/job.json" ]; then
    cat > "${job_root}/job.json" <<EOF
{
  "job_id": "${job_id}",
  "job_schema_version": "1.0",
  "title": "",
  "language": "es",
  "content_type": "short_form",
  "render_targets": ["vertical"],
  "default_target": "vertical",
  "created_at": "",
  "updated_at": "",
  "pipeline_version": "v1"
}
EOF
  fi

  if [ ! -f "${job_root}/status.json" ]; then
    cat > "${job_root}/status.json" <<EOF
{
  "brief_ready": false,
  "script_ready": false,
  "audio_ready": false,
  "subtitles_ready": false,
  "visual_manifest_ready": false,
  "images_ready": false,
  "videos_ready": false,
  "timeline_vertical_ready": false,
  "timeline_horizontal_ready": false,
  "render_vertical_done": false,
  "render_horizontal_done": false,
  "last_step": "created",
  "last_error": null,
  "updated_at": ""
}
EOF
  fi

  echo "OK -> ${job_root}"
  echo
}

for job_id in "${JOB_IDS[@]}"; do
  create_job "${job_id}"
done

echo "Estructura creada en:"
echo "${JOBS_ROOT}"