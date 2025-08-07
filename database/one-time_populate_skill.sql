-- Use a Common Table Expression (CTE) to calculate and rank similarities
WITH RankedSkills AS (
    SELECT
        j.job_id,
        s.skill_id,
        -- Calculate cosine similarity and name the result 'similarity'
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
        j.requirements_embedding IS NOT NULL AND s.embedding IS NOT NULL
)
-- Insert the top 10 ranked skills for each job into the job_skill table
INSERT INTO job_skill (job_id, skill_id, similarity) -- UPDATED: Using the 'similarity' column
SELECT
    job_id,
    skill_id,
    similarity
FROM
    RankedSkills
WHERE
    rn <= 10
ON CONFLICT (job_id, skill_id) DO NOTHING;