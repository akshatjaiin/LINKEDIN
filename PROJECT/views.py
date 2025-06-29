from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from linkedin_api import Linkedin
from openai import OpenAI
import re
import json
import logging
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from . import jobs

# Third-party imports
import mistune
from google import genai
from google.genai import types
from dotenv import load_dotenv
from django.utils.safestring import mark_safe

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
@dataclass
class Config:
    LINKEDIN_EMAIL: str = os.getenv("LINKEDIN_EMAIL")
    LINKEDIN_PASSWORD: str = os.getenv("LINKEDIN_PASSWORD")
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY')
    GEMINI_API_KEY: str = os.getenv('GEMINI_API_KEY')
    
    def __post_init__(self):
        if not all([self.LINKEDIN_EMAIL, self.LINKEDIN_PASSWORD, self.OPENAI_API_KEY]):
            raise ValueError("Missing required environment variables")

config = Config()

# Initialize clients
openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)

class LinkedInAnalyzerService:
    """Service class to handle LinkedIn profile analysis and AI processing"""
    
    @staticmethod
    def extract_linkedin_username(url: str) -> Optional[str]:
        """Extract username from LinkedIn URL with improved regex"""
        if not url:
            return None
            
        # Clean URL and handle various formats
        url = url.strip().lower()
        patterns = [
            r'linkedin\.com/in/([a-zA-Z0-9\-_%]+)/?',
            r'linkedin\.com/pub/([a-zA-Z0-9\-_%]+)/?',
            r'linkedin\.com/profile/view\?id=([a-zA-Z0-9\-_%]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @staticmethod
    def fetch_linkedin_profile(username: str) -> Dict[str, Any]:
        """Fetch LinkedIn profile data with error handling"""
        try:
            # Check cache first
            cache_key = f"linkedin_profile_{username}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Retrieved cached data for {username}")
                return cached_data
            
            # Fetch from LinkedIn API
            api = Linkedin(config.LINKEDIN_EMAIL, config.LINKEDIN_PASSWORD)
            
            profile_data = api.get_profile(username)
            contact_info = api.get_profile_contact_info(username)
            
            # Combine data
            result = {
                'profile': profile_data,
                'contact': contact_info,
                'username': username
            }
            
            # Cache for 1 hour
            cache.set(cache_key, result, 3600)
            logger.info(f"Successfully fetched and cached profile for {username}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching LinkedIn profile for {username}: {str(e)}")
            raise Exception(f"Failed to fetch LinkedIn profile: {str(e)}")
    
    @staticmethod
    def generate_ai_analysis(resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI analysis using OpenAI with improved prompting"""
        try:
            # Create a comprehensive prompt
            analysis_prompt = f"""
            As a professional career advisor and LinkedIn expert, analyze this LinkedIn profile data and provide detailed insights:

            Profile Data: {json.dumps(resume_data, indent=2)}

            Please provide analysis in the following areas:
            1. **Profile Strength Assessment** (Score 1-100)
            2. **Key Strengths** identified in the profile
            3. **Areas for Improvement** with specific recommendations
            4. **Career Progression Analysis**
            5. **Skills Gap Analysis** - what skills are missing for career growth
            6. **Industry Position** - how competitive is this profile in their industry
            7. **Networking Opportunities** - suggestions for expanding professional network
            8. **Content Strategy** - recommendations for LinkedIn content creation
            9. **Profile Optimization Tips** - specific actionable improvements
            10. **Career Path Suggestions** - potential next career moves

            Format your response in clear markdown with headers and bullet points for readability.
            Be specific, actionable, and professional in your recommendations.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert LinkedIn career advisor with 15+ years of experience helping professionals optimize their profiles and advance their careers."
                    },
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            return {
                'analysis': response.choices[0].message.content,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error generating AI analysis: {str(e)}")
            return {
                'analysis': f"Error generating analysis: {str(e)}",
                'success': False
            }
    
    @staticmethod
    def generate_job_recommendations(resume_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate job recommendations using Gemini AI with improved schema"""
        try:
            # Extract key information for better analysis
            profile = resume_data.get('profile', {})
            experience = profile.get('experience', [])
            education = profile.get('education', [])
            skills = profile.get('skills', [])
            
            # Create focused prompt
            analysis_text = f"""
            Analyze this professional profile and recommend suitable job opportunities:
            
            Current Role: {profile.get('headline', 'Not specified')}
            Location: {profile.get('locationName', 'Not specified')}
            Industry: {profile.get('industryName', 'Not specified')}
            
            Recent Experience: {experience[:2] if experience else 'None'}
            Education: {education[:2] if education else 'None'}
            Skills: {[s.get('name', '') for s in skills[:10]] if skills else 'None'}
            
            Based on this information, provide job recommendations.
            """
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=f"{analysis_text}\n\nReturn analysis in the specified JSON format."
                        ),
                    ],
                ),
            ]

            generate_content_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=genai.types.Schema(
                    type=genai.types.Type.OBJECT,
                    required=["JOB_TITLES", "LOCATIONS", "RELATED_DOMAINS", "RECOMMENDATIONS", "ATS_SCORE"],
                    properties={
                        "JOB_TITLES": genai.types.Schema(
                            type=genai.types.Type.ARRAY,
                            items=genai.types.Schema(type=genai.types.Type.STRING),
                        ),
                        "LOCATIONS": genai.types.Schema(
                            type=genai.types.Type.ARRAY,
                            items=genai.types.Schema(type=genai.types.Type.STRING),
                        ),
                        "RELATED_DOMAINS": genai.types.Schema(
                            type=genai.types.Type.ARRAY,
                            items=genai.types.Schema(
                                type=genai.types.Type.OBJECT,
                                required=["domain", "relevance_score"],
                                properties={
                                    "domain": genai.types.Schema(type=genai.types.Type.STRING),
                                    "relevance_score": genai.types.Schema(type=genai.types.Type.INTEGER),
                                },
                            ),
                        ),
                        "RECOMMENDATIONS": genai.types.Schema(
                            type=genai.types.Type.ARRAY,
                            items=genai.types.Schema(type=genai.types.Type.STRING),
                        ),
                        "ATS_SCORE": genai.types.Schema(type=genai.types.Type.INTEGER),
                        "SKILLS_TO_DEVELOP": genai.types.Schema(
                            type=genai.types.Type.ARRAY,
                            items=genai.types.Schema(type=genai.types.Type.STRING),
                        ),
                    },
                ),
            )

            json_string = ""
            for chunk in gemini_client.models.generate_content_stream(
                model="gemini-2.0-flash-lite",
                contents=contents,
                config=generate_content_config,
            ):
                if chunk.text:
                    json_string += chunk.text

            return json.loads(json_string)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating job recommendations: {str(e)}")
            return None

    @staticmethod
    def generate_ats_resume(linkedin_data: Dict[str, Any], job_description: str) -> Optional[str]:
        """Generate ATS-optimized resume using Gemini AI"""
        try:
            prompt = f"""
            As an expert resume writer and ATS specialist, create a tailored, ATS-friendly resume in markdown format based on the LinkedIn profile data and job description provided.

            **Instructions:**
            - Focus on relevant experience, skills, and achievements
            - Make the resume as detailed as possible 
            - Use keywords from the job description naturally throughout
            - Structure with clear sections: Summary, Experience, Skills, Education
            - Use bullet points for achievements with quantifiable results where possible
            - Ensure ATS readability with proper formatting

            **LinkedIn Profile Data:**
            {json.dumps(linkedin_data, indent=2)}

            **Target Job Description:**
            {job_description}

            **Output Format:** Clean markdown with proper headers and formatting.
            """

            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=[types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )]
            )
            
            return response.text if response and response.text else None
            
        except Exception as e:
            logger.error(f"Error generating ATS resume: {str(e)}")
            return None

    @staticmethod
    def update_resume_with_chat(current_resume: str, user_message: str) -> Optional[str]:
        """Update resume based on user chat message"""
        try:
            chat_prompt = f"""
            You are an expert resume writer. I will provide you with a current resume in markdown format and a user request for modifications.

            **Current Resume:**
            {current_resume}

            **User Request:**
            {user_message}

            **Instructions:**
            - Make the requested changes while maintaining ATS-friendly formatting
            - Keep the overall structure and professional tone
            - Only modify what's specifically requested
            - Return the complete updated resume in markdown format
            - Ensure all changes enhance the resume's effectiveness

            **Output:** Return only the updated resume in markdown format, nothing else.
            """

            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=[types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=chat_prompt)]
                )]
            )
            
            return response.text if response and response.text else None
            
        except Exception as e:
            logger.error(f"Error updating resume with chat: {str(e)}")
            return None

# Views
@csrf_exempt
def index(request):
    """Main landing page with LinkedIn URL input"""
    if request.method == 'POST':
        profile_url = request.POST.get('linkedin_url', '').strip()
        
        if not profile_url:
            messages.error(request, 'Please enter a valid LinkedIn URL')
            return render(request, 'index.html')
        
        username = LinkedInAnalyzerService.extract_linkedin_username(profile_url)
        
        if not username:
            messages.error(request, 'Invalid LinkedIn URL format. Please enter a valid LinkedIn profile URL.')
            return render(request, 'index.html')

        try:
            # Fetch LinkedIn data
            linkedin_data = LinkedInAnalyzerService.fetch_linkedin_profile(username)
            
            # Store in session with expiry
            request.session['linkedin_data'] = linkedin_data
            request.session.set_expiry(3600)  # 1 hour
            
            messages.success(request, f'Successfully loaded profile for {username}')
            return redirect('resume')
            
        except Exception as e:
            logger.error(f"Error in index view: {str(e)}")
            messages.error(request, f'Error fetching profile: {str(e)}')
            return render(request, 'index.html')

    return render(request, 'index.html')

def resume(request):
    """Display the formatted resume"""
    if request.method == "POST":
        return redirect('ai_analysis')

    linkedin_data = request.session.get('linkedin_data')
    
    if not linkedin_data:
        messages.warning(request, 'No profile data found. Please enter a LinkedIn URL first.')
        return redirect('index')

    context = {
        'data': linkedin_data.get('profile', {}),
        'contact': linkedin_data.get('contact', {}),
        'username': linkedin_data.get('username', '')
    }
    
    return render(request, 'resume.html', context)

def ai_analysis(request):
    """Generate and display AI analysis of the LinkedIn profile"""
    linkedin_data = request.session.get('linkedin_data')
    
    if not linkedin_data:
        messages.warning(request, 'No profile data found. Please start over.')
        return redirect('index')
    
    try:
        # Generate AI analysis
        ai_analysis_result = LinkedInAnalyzerService.generate_ai_analysis(linkedin_data)
        
        # Generate job recommendations
        job_recommendations = LinkedInAnalyzerService.generate_job_recommendations(linkedin_data)
        
        # Fetch actual job listings if recommendations are available
        jobs_data = []
        if job_recommendations and job_recommendations.get('JOB_TITLES'):
            primary_job_title = job_recommendations['JOB_TITLES'][0]
            primary_location = job_recommendations.get('LOCATIONS', [''])[0] if job_recommendations.get('LOCATIONS') else ''
            
            try:
                jobs_data = jobs.fetch_jobs(primary_job_title, location=primary_location)
                request.session['jobs'] = jobs_data.get('jobs', [])  # Store only the list of jobs
                logger.info(f"Fetched {len(jobs_data.get('jobs', []))} jobs for {primary_job_title}")
            except Exception as e:
                logger.error(f"Error fetching jobs: {str(e)}")
                jobs_data = []
        
        context = {
            'analysis': mistune.html(ai_analysis_result['analysis']),
            'analysis_success': ai_analysis_result['success'],
            'job_recommendations': job_recommendations,
            'jobs_data': jobs_data.get('jobs', []),  # Pass only the list of jobs
            'profile_data': linkedin_data.get('profile', {}),
        }
        
        return render(request, "ai_analysis.html", context)
        
    except Exception as e:
        logger.error(f"Error in ai_analysis view: {str(e)}")
        messages.error(request, f'Error generating analysis: {str(e)}')
        return render(request, "ai_analysis.html", {
            'error': 'Could not analyze LinkedIn data. Please try again.',
            'analysis': '',
            'jobs_data': []
        })

@csrf_protect
def ats_resume(request):
    """Handle ATS resume generation and chat-based modifications"""
    linkedin_data = request.session.get('linkedin_data')
    
    if not linkedin_data:
        messages.warning(request, 'No profile data found. Please start over.')
        return redirect('index')
    
    # Initialize chat history if not exists
    if 'ats_chat_history' not in request.session:
        request.session['ats_chat_history'] = []
    
    ats_resume_md = request.session.get('ats_resume_md')
    
    if request.method == 'POST':
        # Handle initial job description submission
        if 'ats_job_desc' in request.POST:
            job_desc = request.POST.get('ats_job_desc', '').strip()
            
            if not job_desc:
                messages.error(request, 'Please enter a job description.')
                return render(request, 'ats_resume_md.html', {
                    'ats_resume_md': '',
                    'show_job_form': True
                })
            
            try:
                # Generate initial ATS resume
                ats_resume_md = LinkedInAnalyzerService.generate_ats_resume(linkedin_data, job_desc)
                
                if ats_resume_md:
                    request.session['ats_resume_md'] = ats_resume_md
                    request.session['job_description'] = job_desc
                    
                    # Add initial message to chat history
                    request.session['ats_chat_history'] = [{
                        'type': 'system',
                        'message': 'Resume generated successfully! You can now ask me to make modifications.'
                    }]
                    
                    messages.success(request, 'ATS resume generated successfully!')
                else:
                    messages.error(request, 'Failed to generate ATS resume. Please try again.')
                    
            except Exception as e:
                logger.error(f"Error generating ATS resume: {str(e)}")
                messages.error(request, f"Error generating ATS resume: {str(e)}")
        
        # Handle chat message for resume modification
        elif 'chat_message' in request.POST:
            chat_message = request.POST.get('chat_message', '').strip()
            
            if not chat_message or not ats_resume_md:
                messages.error(request, 'Invalid request.')
                return redirect('ats_resume')
            
            try:
                # Add user message to chat history
                chat_history = request.session.get('ats_chat_history', [])
                chat_history.append({
                    'type': 'user',
                    'message': chat_message
                })
                
                # Update resume based on user request
                updated_resume = LinkedInAnalyzerService.update_resume_with_chat(ats_resume_md, chat_message)
                
                if updated_resume:
                    request.session['ats_resume_md'] = updated_resume
                    ats_resume_md = updated_resume
                    
                    # Add success message to chat history
                    chat_history.append({
                        'type': 'ai',
                        'message': 'Resume updated successfully based on your request!'
                    })
                    
                    messages.success(request, 'Resume updated successfully!')
                else:
                    # Add error message to chat history
                    chat_history.append({
                        'type': 'ai',
                        'message': 'Sorry, I couldn\'t update your resume. Please try rephrasing your request.'
                    })
                    
                    messages.error(request, 'Failed to update resume. Please try again.')
                
                request.session['ats_chat_history'] = chat_history
                
            except Exception as e:
                logger.error(f"Error updating ATS resume: {str(e)}")
                messages.error(request, f"Error updating resume: {str(e)}")
    
    # Handle download request
    if request.method == 'GET' and request.GET.get('download') == '1' and ats_resume_md:
        response = HttpResponse(ats_resume_md, content_type='text/markdown')
        response['Content-Disposition'] = 'attachment; filename="ATS_Resume.md"'
        return response
    
    # Determine if we should show the job description form
    show_job_form = not ats_resume_md
    
    context = {
        'ats_resume_md': mistune.html(ats_resume_md) if ats_resume_md else '',
        'ats_resume_raw': ats_resume_md or '',
        'show_job_form': show_job_form,
        'chat_history': request.session.get('ats_chat_history', []),
        'job_description': request.session.get('job_description', ''),
        'profile_data': linkedin_data.get('profile', {}),
    }

    print(f"context: {context}")  # Debugging output
    
    return render(request, 'ats_resume_md.html', context)

def clear_session(request):
    """Clear session data and redirect to index"""
    request.session.flush()
    messages.info(request, 'Session cleared. You can analyze a new profile.')
    return redirect('index')

def clear_ats_session(request):
    """Clear only ATS-related session data"""
    session_keys_to_clear = ['ats_resume_md', 'ats_chat_history', 'job_description']
    
    for key in session_keys_to_clear:
        if key in request.session:
            del request.session[key]
    
    messages.info(request, 'ATS resume session cleared. You can generate a new resume.')
    return redirect('ats_resume')

# API endpoints for AJAX requests
def profile_status_api(request):
    """API endpoint to check if profile data exists in session"""
    has_data = bool(request.session.get('linkedin_data'))
    return JsonResponse({
        'has_profile_data': has_data,
        'username': request.session.get('linkedin_data', {}).get('username', '') if has_data else ''
    })

def jobs_api(request):
    """API endpoint to get cached job data"""
    jobs_data = request.session.get('jobs', [])
    logger.info(f"jobs_api: type={type(jobs_data)}, count={len(jobs_data)}")
    
    # Ensure jobs_data is a list of dicts (JSON serializable)
    if not isinstance(jobs_data, list):
        jobs_data = list(jobs_data)
    jobs_data = [dict(job) if not isinstance(job, dict) else job for job in jobs_data]
    
    return JsonResponse({
        'jobs': jobs_data,
        'count': len(jobs_data)
    })

def ats_chat_api(request):
    """API endpoint for ATS resume chat (for future AJAX implementation)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        chat_message = data.get('message', '').strip()
        
        if not chat_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        ats_resume_md = request.session.get('ats_resume_md')
        if not ats_resume_md:
            return JsonResponse({'error': 'No resume found in session'}, status=404)
        
        # Update resume based on chat message
        updated_resume = LinkedInAnalyzerService.update_resume_with_chat(ats_resume_md, chat_message)
        
        if updated_resume:
            request.session['ats_resume_md'] = updated_resume
            
            # Update chat history
            chat_history = request.session.get('ats_chat_history', [])
            chat_history.extend([
                {'type': 'user', 'message': chat_message},
                {'type': 'ai', 'message': 'Resume updated successfully!'}
            ])
            request.session['ats_chat_history'] = chat_history
            
            return JsonResponse({
                'success': True,
                'updated_resume_html': mark_safe(mistune.html(updated_resume)),
                'updated_resume_raw': updated_resume,
                'chat_history': chat_history
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to update resume'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error in ats_chat_api: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)