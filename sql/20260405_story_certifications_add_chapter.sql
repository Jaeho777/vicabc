ALTER TABLE story_certifications
    MODIFY level_id INT NULL;

ALTER TABLE story_certifications
    ADD COLUMN chapter_id INT NULL AFTER level_id;

ALTER TABLE story_certifications
    ADD INDEX ix_story_certifications_chapter_id (chapter_id);

ALTER TABLE story_certifications
    ADD CONSTRAINT fk_story_certifications_chapter
    FOREIGN KEY (chapter_id) REFERENCES chapters(id);
