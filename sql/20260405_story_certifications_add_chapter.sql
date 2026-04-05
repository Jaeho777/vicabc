SET @schema_name = DATABASE();

SET @should_modify_level_id = (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = @schema_name
      AND table_name = 'story_certifications'
      AND column_name = 'level_id'
      AND is_nullable = 'NO'
);

SET @sql = IF(
    @should_modify_level_id > 0,
    'ALTER TABLE story_certifications MODIFY level_id INT NULL',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @should_add_chapter_id = (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = @schema_name
      AND table_name = 'story_certifications'
      AND column_name = 'chapter_id'
);

SET @sql = IF(
    @should_add_chapter_id = 0,
    'ALTER TABLE story_certifications ADD COLUMN chapter_id INT NULL AFTER level_id',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @should_add_chapter_index = (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = @schema_name
      AND table_name = 'story_certifications'
      AND index_name = 'ix_story_certifications_chapter_id'
);

SET @sql = IF(
    @should_add_chapter_index = 0,
    'ALTER TABLE story_certifications ADD INDEX ix_story_certifications_chapter_id (chapter_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @should_add_chapter_fk = (
    SELECT COUNT(*)
    FROM information_schema.table_constraints
    WHERE table_schema = @schema_name
      AND table_name = 'story_certifications'
      AND constraint_type = 'FOREIGN KEY'
      AND constraint_name = 'fk_story_certifications_chapter'
);

SET @sql = IF(
    @should_add_chapter_fk = 0,
    'ALTER TABLE story_certifications ADD CONSTRAINT fk_story_certifications_chapter FOREIGN KEY (chapter_id) REFERENCES chapters(id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
