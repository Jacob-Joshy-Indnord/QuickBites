-- 0001_create_zones.sql — PostGIS schema for delivery zones (task-ZwUtwpRON0k).
--
-- Creates the `zones` table that stores admin-managed delivery zone polygons.
-- Boundaries are geometry(MultiPolygon, 4326) in WGS 84 lng/lat; a CHECK keeps
-- them topologically valid and another CHECK ties `is_active` to
-- `deactivated_at` so a deactivated zone always records when it was switched
-- off. Indexes: a unique index on lower(name) enforces case-insensitive name
-- uniqueness; a partial GiST index on `boundary` restricted to active rows
-- backs the hot point-in-zone lookup (ST_Covers ... WHERE is_active) and the
-- overlap check run on every create/edit. Zones are never hard-deleted;
-- deactivation is a soft delete. This file defines no functions or triggers.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS zones (
    id              uuid PRIMARY KEY,
    name            text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 100),
    boundary        geometry(MultiPolygon, 4326) NOT NULL CHECK (ST_IsValid(boundary)),
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deactivated_at  timestamptz,
    CONSTRAINT zones_deactivated_at_matches_flag
        CHECK (is_active = (deactivated_at IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS zones_name_lower_uq ON zones (lower(name));

CREATE INDEX IF NOT EXISTS zones_active_boundary_gist
    ON zones USING gist (boundary) WHERE is_active;
