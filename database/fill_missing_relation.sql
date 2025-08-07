-- Use a Common Table Expression (CTE) to calculate and rank similarities
WITH RankedSkills AS (
    SELECT
        j.job_id,
        s.id AS skill_id, -- Use the primary key of the skill table, likely 'id'
        -- Calculate cosine similarity
        1 - (j.requirements_embedding <=> s.embedding) AS similarity,
        -- For each job, rank the skills by their similarity score
        ROW_NUMBER() OVER(
            PARTITION BY j.job_id
            ORDER BY (1 - (j.requirements_embedding <=> s.embedding)) DESC
        ) as rn
    FROM
        job j
    CROSS JOIN
        skill s
    WHERE
        -- Condition 1: Ensure embeddings exist to avoid errors
        j.requirements_embedding IS NOT NULL AND s.embedding IS NOT NULL
        -- Condition 2: Only include jobs that are NOT already in the job_skill table
        AND NOT EXISTS (
            SELECT 1
            FROM job_skill js
            WHERE js.job_id = j.job_id
        )
)
-- Insert the top 10 ranked skills for each new job into the job_skill table
INSERT INTO job_skill (job_id, skill_id, similarity)
SELECT
    job_id,
    skill_id,
    similarity
FROM
    RankedSkills
WHERE
    rn <= 10
-- ON CONFLICT is good practice but less critical here, as we've pre-filtered jobs.
-- It remains a good safety net against race conditions.
ON CONFLICT (job_id, skill_id) DO NOTHING;