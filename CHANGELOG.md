# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **CBZ archive creation**: after an album finishes downloading, all images are packaged
  into a `.cbz` comic archive (zero-padded for correct page order) saved in the `Downloads`
  folder.
- **Resume support**: already-downloaded images are detected and skipped, so an interrupted
  run can be restarted without re-downloading the pages it already has.

## [1.0.1] - 2026-03-19

### Changed

- Migrated project to a `src/` layout for a cleaner, more modular structure.

## [1.0.0] - 2025-08-04

### Added

- Single-album and batch downloads from E-Hentai URLs.
- Concurrent image downloads with rate limiting and retry handling.
- Live progress tracking and session logging.