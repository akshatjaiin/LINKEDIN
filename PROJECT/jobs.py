from jobspy import scrape_jobs
import pandas as pd
import json
import csv
def fetch_jobs(search_term: str, location: str = "JAIPUR, IN", results: int = 10, 
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
            "site_name": ["indeed", "linkedin", "naukri"],
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
            search_params["country_indeed"] = 'india'
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
        for idx, job in jobs.head(len(jobs)).iterrows():  # Show more jobs for better matching
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
        
        return result
        
    except Exception as e:
        error_msg = f"Error occurred while fetching jobs: {str(e)}"
        print(f"[ERROR] {error_msg}")
        import traceback
        traceback.print_exc()
        return error_msg
