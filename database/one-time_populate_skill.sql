-- Clear the table before populating to avoid duplicates if run multiple times
TRUNCATE TABLE job_skill;

-- Use a Common Table Expression (CTE) to calculate and rank similarities
WITH RankedSkills AS (
    SELECT
        j.job_id,
        s.skill_id,                        
        1 - (j.requirements_embedding <=> s.embedding) AS similarity_score,
        ROW_NUMBER() OVER(
            PARTITION BY j.job_id               -- This is correct
            ORDER BY (1 - (j.requirements_embedding <=> s.embedding)) DESC
        ) as rn
    FROM
        job j
    CROSS JOIN
        skill s
    WHERE
        j.requirements_embedding IS NOT NULL AND s.embedding IS NOT NULL
)
-- Insert the top 10 ranked skills for each job into the job_skill table
INSERT INTO job_skill (job_id, skill_id, relevance) -- CORRECTED: Was 'similarity'
SELECT
    job_id,
    skill_id,
    similarity_score                            -- Use the alias from the CTE
FROM
    RankedSkills
WHERE
    rn <= 10;