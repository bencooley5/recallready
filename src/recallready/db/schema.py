"""Trusted SQLite DDL for the derived RecallReady query database."""

from __future__ import annotations

SCHEMA_VERSION = "1.0.0"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE recall_records (
  source_record_id TEXT PRIMARY KEY, source_agency TEXT NOT NULL,
  recall_number TEXT, event_id TEXT, report_date TEXT, recall_initiation_date TEXT,
  center_classification_date TEXT, termination_date TEXT, classification TEXT,
  source_status TEXT, recalling_firm TEXT, firm_normalized TEXT, city TEXT,
  state TEXT, country TEXT, product_description TEXT, product_quantity TEXT,
  product_code TEXT, code_info TEXT, reason_for_recall TEXT,
  distribution_pattern TEXT, initial_firm_notification TEXT,
  voluntary_mandated TEXT, product_type TEXT, reporting_lag_days INTEGER,
  derived_product_category TEXT NOT NULL, raw_json TEXT NOT NULL,
  source_last_updated TEXT, ingested_at TEXT NOT NULL
);
CREATE TABLE recall_tags (
  source_record_id TEXT NOT NULL REFERENCES recall_records(source_record_id) ON DELETE CASCADE,
  tag_type TEXT NOT NULL, tag_value TEXT NOT NULL, rule_id TEXT NOT NULL,
  confidence_label TEXT NOT NULL, taxonomy_version TEXT NOT NULL,
  PRIMARY KEY (source_record_id, rule_id)
);
CREATE TABLE ingestion_runs (
  run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT NOT NULL,
  source_agency TEXT NOT NULL, source_last_updated TEXT, source_total_matches INTEGER,
  record_count INTEGER NOT NULL, tag_count INTEGER NOT NULL, validation_outcome TEXT NOT NULL,
  code_version TEXT NOT NULL, schema_version TEXT NOT NULL
);
CREATE VIRTUAL TABLE recall_records_fts USING fts5(
  recalling_firm, product_description, reason_for_recall, code_info, distribution_pattern,
  content='recall_records', content_rowid='rowid'
);
CREATE TRIGGER recall_records_ai AFTER INSERT ON recall_records BEGIN
  INSERT INTO recall_records_fts(rowid, recalling_firm, product_description, reason_for_recall, code_info, distribution_pattern)
  VALUES (new.rowid, new.recalling_firm, new.product_description, new.reason_for_recall, new.code_info, new.distribution_pattern);
END;
CREATE TRIGGER recall_records_ad AFTER DELETE ON recall_records BEGIN
  INSERT INTO recall_records_fts(recall_records_fts, rowid, recalling_firm, product_description, reason_for_recall, code_info, distribution_pattern)
  VALUES ('delete', old.rowid, old.recalling_firm, old.product_description, old.reason_for_recall, old.code_info, old.distribution_pattern);
END;
CREATE TRIGGER recall_records_au AFTER UPDATE ON recall_records BEGIN
  INSERT INTO recall_records_fts(recall_records_fts, rowid, recalling_firm, product_description, reason_for_recall, code_info, distribution_pattern)
  VALUES ('delete', old.rowid, old.recalling_firm, old.product_description, old.reason_for_recall, old.code_info, old.distribution_pattern);
  INSERT INTO recall_records_fts(rowid, recalling_firm, product_description, reason_for_recall, code_info, distribution_pattern)
  VALUES (new.rowid, new.recalling_firm, new.product_description, new.reason_for_recall, new.code_info, new.distribution_pattern);
END;
CREATE INDEX idx_records_report_date ON recall_records(report_date);
CREATE INDEX idx_records_classification ON recall_records(classification);
CREATE INDEX idx_records_event_id ON recall_records(event_id);
CREATE INDEX idx_records_recall_number ON recall_records(recall_number);
CREATE INDEX idx_records_firm_normalized ON recall_records(firm_normalized);
CREATE INDEX idx_records_state ON recall_records(state);
CREATE INDEX idx_records_category ON recall_records(derived_product_category);
CREATE INDEX idx_tags_value ON recall_tags(tag_value);
"""
