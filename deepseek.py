from openai import OpenAI

client = OpenAI(api_key="sk-91264fc70f824a19be25eb00e3148039", base_url="https://api.deepseek.com")

with open(r"C:\Users\Dang\Desktop\jobs_crawler\instruction.md", "r", encoding="utf-8") as f:
    instruction_content = f.read()

content = f"""
Giới thiệu việc làm Overview As a global tech company, we empower businesses with tailored tech and business solutions that drive innovation and sustainable growth. With over 3,000 experts across 21 countries, we deliver results through flexible engagement models—whether augmenting teams, managing complex projects, or building long-term operations. We specialize in Strategy & Governance, Product Design & Growth, Software Engineering, Data Analytics & AI, Cloud & Enterprise Platforms, Cybersecurity, and industry-specific solutions for Banking, Life Sciences, and Smart Industrial sectors. Guided by our commitment to building a better world, we dedicate time, resources, and expertise to education projects, creating a lasting impact on our teams, communities, and planet. What you will do: Design, implement, and manage Cloud infrastructure using the IaC approach Manage containerized applications and orchestrate them Collaborate with development teams to support and improve deployment processes Build and maintain CI/CD pipelines for multiple public services Maintain and optimize PostgreSQL databases Monitor and ensure systems and services reliability and performance Troubleshoot and resolve infrastructure and application issues across environments Ensure security best practices are followed across all systems and deployments Document processes and configurations clearly and effectively Required Skills and Qualifications: Strong experience with Linux systems and scripting using Bash and Python Solid understanding of networking concepts and troubleshooting Hands-on experience with containerization and orchestration tools like Docker Proficiency in AWS cloud services and architecture, including VPC, S3, EBS, RDS, EC2, ECS, Fargate, EKS and others Experience with IaC tools: Terraform, Terragrunt, Atlantis, Ansible Deep knowledge of Kubernetes and its ecosystem Experience with CI/CD tools: GitHub Actions, ArgoCD / Flux, Helm Familiarity with observability tools: Prometheus, Grafana, Loki/ELK, DataDog, PagerDuty Strong understanding of version control systems, especially Git Excellent analytical and problem-solving skills Strong communication skills and ability to work collaboratively in a team Fluent English speaking and writing skills
"""



response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": instruction_content},
        {"role": "user", "content": content},
    ],
    stream=False
)

print(response.choices[0].message.content)