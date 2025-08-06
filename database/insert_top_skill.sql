-- 1. Create the function that will be executed by the trigger
CREATE OR REPLACE FUNCTION insert_top_job_skills()
RETURNS TRIGGER AS $$
BEGIN
    -- This condition checks if the newly inserted job has a non-NULL embedding.
    -- If it's NULL, the function does nothing and exits gracefully.
    IF NEW.requirements_embedding IS NOT NULL THEN

        -- The INSERT statement will only run if the condition above is true.
        INSERT INTO job_skill (job_id, skill_id, relevance) -- CORRECTED: Column name is 'relevance'
        SELECT
            NEW.job_id,  -- CORRECTED: Column name is 'job_id'
            s.skill_id,  -- CORRECTED: Column name is 'skill_id'
            1 - (NEW.requirements_embedding <=> s.embedding) AS similarity_score
        FROM
            skill s
        WHERE
            s.embedding IS NOT NULL -- Also good practice to ensure skills have embeddings
        ORDER BY
            similarity_score DESC -- Order by the calculated similarity
        LIMIT 10;

    END IF;

    -- The RETURN NEW statement is required for AFTER triggers.
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Drop the existing trigger to ensure a clean setup (optional but good practice)
DROP TRIGGER IF EXISTS trigger_insert_job_skills ON job;

-- 3. Create the trigger that calls the function after a new job is inserted
CREATE TRIGGER trigger_insert_job_skills
AFTER INSERT ON job
FOR EACH ROW
EXECUTE FUNCTION insert_top_job_skills();