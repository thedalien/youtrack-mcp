"""
YouTrack Issues API client.
"""
from typing import Any, Dict, List, Optional
import json
import logging

from pydantic import BaseModel, Field

from youtrack_mcp.api.client import YouTrackClient, YouTrackAPIError

logger = logging.getLogger(__name__)


class Issue(BaseModel):
    """Model for a YouTrack issue."""
    
    id: str
    summary: Optional[str] = None
    description: Optional[str] = None
    created: Optional[int] = None
    updated: Optional[int] = None
    project: Dict[str, Any] = Field(default_factory=dict)
    reporter: Optional[Dict[str, Any]] = None
    assignee: Optional[Dict[str, Any]] = None
    custom_fields: List[Dict[str, Any]] = Field(default_factory=list)
    
    model_config = {
        "extra": "allow",  # Allow extra fields from the API
        "populate_by_name": True  # Allow population by field name (helps with aliases)
    }


class IssuesClient:
    """Client for interacting with YouTrack Issues API."""
    
    def __init__(self, client: YouTrackClient):
        """
        Initialize the Issues API client.
        
        Args:
            client: The YouTrack API client
        """
        self.client = client
    
    def get_issue(self, issue_id: str) -> Issue:
        """
        Get an issue by ID.
        
        Args:
            issue_id: The issue ID or readable ID (e.g., PROJECT-123)
            
        Returns:
            The issue data
        """
        response = self.client.get(f"issues/{issue_id}")
        
        # If the response doesn't have all needed fields, fetch more details
        if isinstance(response, dict) and response.get('$type') == 'Issue' and 'summary' not in response:
            # Get additional fields we need
            fields = "summary,description,created,updated,project,reporter,assignee,customFields"
            detailed_response = self.client.get(f"issues/{issue_id}?fields={fields}")
            return Issue.model_validate(detailed_response)
        
        return Issue.model_validate(response)
    
    def create_issue(self, 
                     project_id: str, 
                     summary: str, 
                     description: Optional[str] = None,
                     additional_fields: Optional[Dict[str, Any]] = None) -> Issue:
        """
        Create a new issue.
        
        Args:
            project_id: The ID of the project
            summary: The issue summary
            description: The issue description
            additional_fields: Additional fields to set on the issue
            
        Returns:
            The created issue data
        """
        # Make sure we have valid input data
        if not project_id:
            raise ValueError("Project ID is required")
        if not summary:
            raise ValueError("Summary is required")
            
        # Format request data according to YouTrack API requirements
        # Note: YouTrack API requires a specific format for some fields
        data = {
            "project": {
                "id": project_id
            },
            "summary": summary
        }
        
        if description:
            data["description"] = description
            
        if additional_fields:
            data.update(additional_fields)
        
        try:
            # For debugging
            logger.info(f"Creating issue with data: {json.dumps(data)}")
            
            # Post directly with the json parameter to ensure correct format
            url = "issues"
            response = self.client.session.post(
                f"{self.client.base_url}/{url}",
                json=data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            
            # Handle the response
            if response.status_code >= 400:
                error_msg = f"Error creating issue: {response.status_code}"
                try:
                    error_content = response.json()
                    error_msg += f" - {json.dumps(error_content)}"
                except:
                    error_msg += f" - {response.text}"
                    
                logger.error(error_msg)
                raise YouTrackAPIError(error_msg, response.status_code, response)
                
            # Process successful response
            try:
                result = response.json()
                return Issue.model_validate(result)
            except Exception as e:
                logger.error(f"Error parsing response: {str(e)}")
                # Return raw response if we can't parse it
                return Issue(id=str(response.status_code), summary="Created successfully")
                
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error creating issue: {str(e)}, Data: {data}")
            raise
    
    def update_issue(self, 
                     issue_id: str, 
                     summary: Optional[str] = None,
                     description: Optional[str] = None,
                     additional_fields: Optional[Dict[str, Any]] = None) -> Issue:
        """
        Update an existing issue.
        
        Args:
            issue_id: The issue ID or readable ID
            summary: The new issue summary
            description: The new issue description
            additional_fields: Additional fields to update
            
        Returns:
            The updated issue data
        """
        data = {}
        
        if summary is not None:
            data["summary"] = summary
            
        if description is not None:
            data["description"] = description
            
        if additional_fields:
            data.update(additional_fields)
            
        if not data:
            # Nothing to update
            return self.get_issue(issue_id)
            
        response = self.client.post(f"issues/{issue_id}", data=data)
        return Issue.model_validate(response)
    
    def search_issues(self, query: str, limit: int = 10) -> List[Issue]:
        """
        Search for issues using YouTrack query language.
        
        Args:
            query: The search query
            limit: Maximum number of issues to return
            
        Returns:
            List of matching issues
        """
        # Request additional fields to ensure we get summary
        fields = "id,summary,description,created,updated,project,reporter,assignee,customFields"
        params = {"query": query, "$top": limit, "fields": fields}
        response = self.client.get("issues", params=params)
        
        issues = []
        for item in response:
            try:
                issues.append(Issue.model_validate(item))
            except Exception as e:
                # Log the error but continue processing other issues
                import logging
                logging.getLogger(__name__).warning(f"Failed to validate issue: {str(e)}")
        
        return issues
    
    def get_issue_comments(self, issue_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get comments for a specific issue.
        
        Args:
            issue_id: The issue ID or readable ID (e.g., PROJECT-123)
            limit: Maximum number of comments to return (optional)
            
        Returns:
            List of comments for the issue
        """
        # Specify fields to retrieve for comments
        fields = "id,text,author(id,login,name),created"
        params = {"fields": fields}
        
        if limit is not None:
            params["$top"] = limit
            
        return self.client.get(f"issues/{issue_id}/comments", params=params)
    
    def add_comment(self, issue_id: str, text: str) -> Dict[str, Any]:
        """
        Add a comment to an issue.
        
        Args:
            issue_id: The issue ID or readable ID
            text: The comment text
            
        Returns:
            The created comment data
        """
        data = {"text": text}
        return self.client.post(f"issues/{issue_id}/comments", data=data) 