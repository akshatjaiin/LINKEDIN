import csv
import json
from openai import OpenAI
from jobspy import scrape_jobs
import pandas as pd

# Initialize OpenAI client
client = OpenAI(api_key="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")

def fetch_jobs(search_term: str, location: str = "San Francisco, CA", results: int = 10, 
               job_type: str = None, is_remote: bool = False, hours_old: int = 72):
    """
    Scrapes recent job listings from multiple job boards using JobSpy
    """
    print(f"\n[INFO] AI decided to search for jobs...")
    print(f"[INFO] Search term: {search_term}")
    print(f"[INFO] Location: {location}")
    print(f"[INFO] Results wanted: {results}")
    print(f"[INFO] Job type: {job_type}")
    print(f"[INFO] Remote: {is_remote}")
    print(f"[INFO] Hours old: {hours_old}")
    
    try:
        # Configure job search parameters
        search_params = {
            "site_name": ["indeed", "linkedin", "glassdoor"],
            "search_term": search_term,
            "location": location,
            "results_wanted": results,
            "hours_old": hours_old,
            "is_remote": is_remote,
        }
        
        # Add job type if specified
        if job_type and job_type.lower() in ['fulltime', 'parttime', 'internship', 'contract']:
            search_params["job_type"] = job_type.lower()
            
        # Set country based on location
        if any(country in location.upper() for country in ['INDIA', 'IN']):
            # For India, don't set country_indeed as it might cause issues
            pass
        elif any(country in location.upper() for country in ['USA', 'US', 'UNITED STATES']):
            search_params["country_indeed"] = 'USA'
            
        # Add google search term for better results
        search_params["google_search_term"] = f"{search_term} jobs {location}"
        
        print(f"[INFO] Scraping jobs from job boards...")
        jobs = scrape_jobs(**search_params)
        
        if len(jobs) == 0:
            return f"No jobs found for '{search_term}' in '{location}'. Try different keywords or location."
        
        # Save to CSV
        csv_filename = f"jobs_{search_term.replace(' ', '_')}_{location.replace(' ', '_').replace(',', '')}.csv"
        jobs.to_csv(csv_filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        
        # Format results for AI response - handle pandas DataFrame properly
        job_summary = []
        for idx, job in jobs.head(min(10, len(jobs))).iterrows():  # Show more jobs for better matching
            job_info = {
                "title": str(job.get('title', 'N/A')),
                "company": str(job.get('company', 'N/A')),
                "location": str(job.get('location', 'N/A')),
                "salary": str(job.get('min_amount', 'N/A')) if pd.notna(job.get('min_amount')) else 'N/A',
                "job_url": str(job.get('job_url', 'N/A')),
                "site": str(job.get('site', 'N/A')),
                "date_posted": str(job.get('date_posted', 'N/A')),
                "description": str(job.get('description', 'N/A'))[:500] + "..." if pd.notna(job.get('description')) else 'N/A'  # Truncate description
            }
            job_summary.append(job_info)
        
        result = {
            "total_jobs_found": len(jobs),
            "csv_saved_as": csv_filename,
            "jobs": job_summary,  # Removed "top_" prefix
            "summary": f"Found {len(jobs)} jobs for '{search_term}' in '{location}'. {len(job_summary)} jobs returned for analysis."
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        error_msg = f"Error occurred while fetching jobs: {str(e)}"
        print(f"[ERROR] {error_msg}")
        import traceback
        traceback.print_exc()
        return error_msg



# Define available functions for OpenAI
tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_jobs",
            "description": "Scrapes recent job listings from multiple job boards (Indeed, LinkedIn, Glassdoor). Returns actual job data including company names, salaries, job URLs, and descriptions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "The job title or keyword to search for, e.g., 'Python Developer', 'Software Engineer', 'Data Scientist'"
                    },
                    "location": {
                        "type": "string", 
                        "description": "The city, state, or country to search in, e.g., 'Jaipur, India', 'San Francisco, CA', 'New York, NY'"
                    },
                    "results": {
                        "type": "number",
                        "description": "Number of job results to fetch (default: 10, recommended: 10-20 for good results)"
                    },
                    "job_type": {
                        "type": "string",
                        "description": "Type of job: 'fulltime', 'parttime', 'internship', 'contract'"
                    },
                    "is_remote": {
                        "type": "boolean",
                        "description": "Whether to search for remote jobs only (true/false)"
                    },
                    "hours_old": {
                        "type": "number",
                        "description": "Filter jobs posted within this many hours (default: 72, use 24 for very recent jobs)"
                    }
                },
                "required": ["search_term", "location"]
            }
        }
    }
]

def analyze_resume_and_find_jobs(resume_dict: dict, location: str = None, job_type: str = "fulltime", results: int = 15):
    """
    Analyze resume and automatically find matching jobs
    """
    print("\n[INFO] Analyzing resume to find matching jobs...")
    
    # Create a comprehensive prompt for GPT to analyze resume
    resume_analysis_prompt = f"""
    Analyze this resume data and determine the best job search strategy:
    
    Resume: {json.dumps(resume_dict, indent=2)}
    
    Based on this resume, please:
    1. Identify the person's primary skills and experience
    2. Determine their career level (junior/mid/senior)  
    3. Suggest 2-3 relevant job search terms that would find the best matches
    4. If location is not provided, try to infer from resume or ask
    5. Automatically call fetch_jobs() with the most relevant search term
    
    Location preference: {location if location else "Not specified - please infer or ask"}
    Preferred job type: {job_type}
    
    Be direct and action-oriented - analyze the resume and immediately search for jobs.
    """
    
    return resume_analysis_prompt

def chat_with_resume_ai(resume_dict: dict = None):
    """
    Main function to handle resume analysis and job matching
    """
    print("🤖 AI Resume & Job Matching Assistant")
    print("=" * 50)
    
    if resume_dict:
        print("📄 Resume loaded! I'll analyze it and find matching jobs.")
        print("You can also ask me to:")
        print("- 'Find jobs for my resume in [location]'")
        print("- 'Search for remote jobs matching my skills'") 
        print("- 'What jobs match my experience level?'")
    else:
        print("Ask me to find jobs! Examples:")
        print("- 'Find Python developer jobs in Jaipur'")
        print("- 'Search for remote software engineering jobs'")
    
    print("Type 'quit' to exit\n")
    
    available_functions = {
        "fetch_jobs": fetch_jobs,
    }
    
    # Initialize conversation with system message
    system_content = """You are an expert resume analyzer and job matching assistant. 

When given a resume, you should:
1. Analyze the person's skills, experience, and career level
2. Automatically call fetch_jobs() to find relevant positions
3. Match jobs to the person's profile and provide personalized recommendations
4. Be direct - don't ask for permission, just analyze and search

When analyzing jobs against a resume, consider:
- Skill alignment (technical and soft skills)
- Experience level requirements
- Location preferences
- Career progression opportunities
- Company culture fit based on background

Always provide specific, actionable job recommendations with reasoning."""
    
    messages = [{"role": "system", "content": system_content}]
    
    # If resume is provided, automatically analyze it
    if resume_dict:
        resume_prompt = analyze_resume_and_find_jobs(resume_dict)
        messages.append({"role": "user", "content": resume_prompt})
        
        # Automatically get AI analysis
        try:
            print("🔍 AI is analyzing your resume...")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            
            # Process the response
            response_message = response.choices[0].message
            messages.append(response_message)
            
            if response_message.tool_calls:
                print("🛠️ AI is searching for jobs based on your resume...\n")
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions[function_name]
                    function_args = json.loads(tool_call.function.arguments)
                    
                    print(f"[EXECUTING] {function_name} with args: {function_args}")
                    function_response = function_to_call(**function_args)
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_response),
                    })
                
                # Get final analysis
                final_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                )
                
                final_answer = final_response.choices[0].message.content
                print(f"\n🤖 AI Resume Analysis & Job Recommendations:\n{final_answer}\n")
                print("-" * 50)
                
                messages.append({"role": "assistant", "content": final_answer})
            else:
                print(f"\n🤖 AI: {response_message.content}\n")
                messages.append({"role": "assistant", "content": response_message.content})
                
        except Exception as e:
            print(f"❌ Error analyzing resume: {str(e)}")
    
    # Continue with interactive chat
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("👋 Goodbye! Good luck with your job search!")
            break
            
        if not user_input:
            continue
            
        messages.append({"role": "user", "content": user_input})
        
        try:
            print("\n🔍 AI is thinking...")
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            
            response_message = response.choices[0].message
            
            if response_message.tool_calls:
                print("🛠️ AI is using tools to help you...\n")
                messages.append(response_message)
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions[function_name]
                    function_args = json.loads(tool_call.function.arguments)
                    
                    print(f"[EXECUTING] {function_name} with args: {function_args}")
                    function_response = function_to_call(**function_args)
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_response),
                    })
                
                second_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                )
                
                final_answer = second_response.choices[0].message.content
                print(f"\n🤖 AI: {final_answer}\n")
                print("-" * 50)
                
                messages.append({"role": "assistant", "content": final_answer})
                
            else:
                print(f"\n🤖 AI: {response_message.content}\n")
                print("-" * 50)
                
                messages.append({"role": "assistant", "content": response_message.content})
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print("Please try again.\n")

if __name__ == "__main__":
    # Replace with your actual OpenAI API key
    if "YOUR_OPENAI_API_KEY_HERE" in client.api_key:
        print("⚠️  Please replace 'YOUR_OPENAI_API_KEY_HERE' with your actual OpenAI API key!")
        print("You can get one from: https://platform.openai.com/api-keys")
    else:
        # Example resume dictionary - replace with actual resume data
        sample_resume = {
            "name": "John Doe",
            "email": "john.doe@email.com",
            "location": "Jaipur, India",
            "experience_years": 3,
            "skills": ["Python", "Django", "JavaScript", "React", "SQL", "Git"],
            "experience": [
                {
                    "company": "Tech Company",
                    "role": "Software Developer", 
                    "duration": "2021-2024",
                    "description": "Developed web applications using Python and Django"
                }
            ],
            "education": "B.Tech Computer Science",
            "career_level": "mid"
        }
        
        # You can either:
        # 1. Pass a resume dictionary to analyze automatically
        # chat_with_resume_ai(sample_resume)
        
        # 2. Or start without resume for manual job search
        chat_with_resume_ai()
        
        # To use with your own resume, replace sample_resume with your resume dict:
        # my_resume = {"name": "Your Name", "skills": [...], ...}
        # chat_with_resume_ai(my_resume)import csv
import json
from openai import OpenAI
from jobspy import scrape_jobs
import pandas as pd

# Initialize OpenAI client
client = OpenAI(api_key="YOUR_OPENAI_API_KEY_HERE")




# Define available functions for OpenAI
tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_jobs",
            "description": "Scrapes recent job listings from multiple job boards (Indeed, LinkedIn, Glassdoor). Returns actual job data including company names, salaries, job URLs, and descriptions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "The job title or keyword to search for, e.g., 'Python Developer', 'Software Engineer', 'Data Scientist'"
                    },
                    "location": {
                        "type": "string", 
                        "description": "The city, state, or country to search in, e.g., 'Jaipur, India', 'San Francisco, CA', 'New York, NY'"
                    },
                    "results": {
                        "type": "number",
                        "description": "Number of job results to fetch (default: 10, recommended: 10-20 for good results)"
                    },
                    "job_type": {
                        "type": "string",
                        "description": "Type of job: 'fulltime', 'parttime', 'internship', 'contract'"
                    },
                    "is_remote": {
                        "type": "boolean",
                        "description": "Whether to search for remote jobs only (true/false)"
                    },
                    "hours_old": {
                        "type": "number",
                        "description": "Filter jobs posted within this many hours (default: 72, use 24 for very recent jobs)"
                    }
                },
                "required": ["search_term", "location"]
            }
        }
    }
]

def analyze_resume_and_find_jobs(resume_dict: dict, location: str = None, job_type: str = "fulltime", results: int = 15):
    """
    Analyze resume and automatically find matching jobs
    """
    print("\n[INFO] Analyzing resume to find matching jobs...")
    
    # Create a comprehensive prompt for GPT to analyze resume
    resume_analysis_prompt = f"""
    Analyze this resume data and determine the best job search strategy:
    
    Resume: {json.dumps(resume_dict, indent=2)}
    
    Based on this resume, please:
    1. Identify the person's primary skills and experience
    2. Determine their career level (junior/mid/senior)  
    3. Suggest 2-3 relevant job search terms that would find the best matches
    4. If location is not provided, try to infer from resume or ask
    5. Automatically call fetch_jobs() with the most relevant search term
    
    Location preference: {location if location else "Not specified - please infer or ask"}
    Preferred job type: {job_type}
    
    Be direct and action-oriented - analyze the resume and immediately search for jobs.
    """
    
    return resume_analysis_prompt

def chat_with_resume_ai(resume_dict: dict = None):
    """
    Main function to handle resume analysis and job matching
    """
    print("🤖 AI Resume & Job Matching Assistant")
    print("=" * 50)
    
    if resume_dict:
        print("📄 Resume loaded! I'll analyze it and find matching jobs.")
        print("You can also ask me to:")
        print("- 'Find jobs for my resume in [location]'")
        print("- 'Search for remote jobs matching my skills'") 
        print("- 'What jobs match my experience level?'")
    else:
        print("Ask me to find jobs! Examples:")
        print("- 'Find Python developer jobs in Jaipur'")
        print("- 'Search for remote software engineering jobs'")
    
    print("Type 'quit' to exit\n")
    
    available_functions = {
        "fetch_jobs": fetch_jobs,
    }
    
    # Initialize conversation with system message
    system_content = """You are an expert resume analyzer and job matching assistant. 

When given a resume, you should:
1. Analyze the person's skills, experience, and career level
2. Automatically call fetch_jobs() to find relevant positions
3. Match jobs to the person's profile and provide personalized recommendations
4. Be direct - don't ask for permission, just analyze and search

When analyzing jobs against a resume, consider:
- Skill alignment (technical and soft skills)
- Experience level requirements
- Location preferences
- Career progression opportunities
- Company culture fit based on background

Always provide specific, actionable job recommendations with reasoning."""
    
    messages = [{"role": "system", "content": system_content}]
    
    # If resume is provided, automatically analyze it
    if resume_dict:
        resume_prompt = analyze_resume_and_find_jobs(resume_dict)
        messages.append({"role": "user", "content": resume_prompt})
        
        # Automatically get AI analysis
        try:
            print("🔍 AI is analyzing your resume...")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            
            # Process the response
            response_message = response.choices[0].message
            messages.append(response_message)
            
            if response_message.tool_calls:
                print("🛠️ AI is searching for jobs based on your resume...\n")
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions[function_name]
                    function_args = json.loads(tool_call.function.arguments)
                    
                    print(f"[EXECUTING] {function_name} with args: {function_args}")
                    function_response = function_to_call(**function_args)
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_response),
                    })
                
                # Get final analysis
                final_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                )
                
                final_answer = final_response.choices[0].message.content
                print(f"\n🤖 AI Resume Analysis & Job Recommendations:\n{final_answer}\n")
                print("-" * 50)
                
                messages.append({"role": "assistant", "content": final_answer})
            else:
                print(f"\n🤖 AI: {response_message.content}\n")
                messages.append({"role": "assistant", "content": response_message.content})
                
        except Exception as e:
            print(f"❌ Error analyzing resume: {str(e)}")
    
    # Continue with interactive chat
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("👋 Goodbye! Good luck with your job search!")
            break
            
        if not user_input:
            continue
            
        messages.append({"role": "user", "content": user_input})
        
        try:
            print("\n🔍 AI is thinking...")
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            
            response_message = response.choices[0].message
            
            if response_message.tool_calls:
                print("🛠️ AI is using tools to help you...\n")
                messages.append(response_message)
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions[function_name]
                    function_args = json.loads(tool_call.function.arguments)
                    
                    print(f"[EXECUTING] {function_name} with args: {function_args}")
                    function_response = function_to_call(**function_args)
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_response),
                    })
                
                second_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                )
                
                final_answer = second_response.choices[0].message.content
                print(f"\n🤖 AI: {final_answer}\n")
                print("-" * 50)
                
                messages.append({"role": "assistant", "content": final_answer})
                
            else:
                print(f"\n🤖 AI: {response_message.content}\n")
                print("-" * 50)
                
                messages.append({"role": "assistant", "content": response_message.content})
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print("Please try again.\n")

if __name__ == "__main__":
    # Replace with your actual OpenAI API key
    if "YOUR_OPENAI_API_KEY_HERE" in client.api_key:
        print("⚠️  Please replace 'YOUR_OPENAI_API_KEY_HERE' with your actual OpenAI API key!")
        print("You can get one from: https://platform.openai.com/api-keys")
    else:
        # Example resume dictionary - replace with actual resume data
        sample_resume = {
            "name": "John Doe",
            "email": "john.doe@email.com",
            "location": "Jaipur, India",
            "experience_years": 3,
            "skills": ["Python", "Django", "JavaScript", "React", "SQL", "Git"],
            "experience": [
                {
                    "company": "Tech Company",
                    "role": "Software Developer", 
                    "duration": "2021-2024",
                    "description": "Developed web applications using Python and Django"
                }
            ],
            "education": "B.Tech Computer Science",
            "career_level": "mid"
        }
        
        # You can either:
        # 1. Pass a resume dictionary to analyze automatically
        # chat_with_resume_ai(sample_resume)
        
        # 2. Or start without resume for manual job search
        chat_with_resume_ai()
        
        # To use with your own resume, replace sample_resume with your resume dict:
        # my_resume = {"name": "Your Name", "skills": [...], ...}
        # chat_with_resume_ai(my_resume)