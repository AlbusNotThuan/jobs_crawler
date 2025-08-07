-- Step 1: Drop the function first, only if it already exists.
DROP FUNCTION IF EXISTS insert_top_job_skills();

-- Step 2: Now, create the function from scratch.
CREATE FUNCTION insert_top_job_skills()
RETURNS TRIGGER AS $$
BEGIN
    -- This condition checks if the newly inserted job has a non-NULL embedding.
    IF NEW.requirements_embedding IS NOT NULL THEN

        -- The INSERT statement will only run if the condition above is true.
        INSERT INTO job_skill (job_id, skill_id, similarity)
        SELECT
            NEW.job_id,
            s.skill_id,
            1 - (NEW.requirements_embedding <=> s.embedding) AS similarity_score
        FROM
            skill s
        WHERE
            s.embedding IS NOT NULL
        ORDER BY
            similarity_score DESC
        LIMIT 10;
    END IF;

    -- The RETURN NEW statement is required for AFTER triggers.
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 3: Drop the existing trigger to ensure a clean setup
DROP TRIGGER IF EXISTS trigger_insert_job_skills ON job;

-- Step 4: Create the trigger that calls the function
CREATE TRIGGER trigger_insert_job_skills
AFTER INSERT ON job
FOR EACH ROW
EXECUTE FUNCTION insert_top_job_skills();