"""Cache warming utilities for preloading frequently accessed data on startup.

**Validates: Requirements 28.1, 28.2, 28.3, 28.4**

This module provides cache warming functionality to preload document metadata
and other frequently accessed data into Redis on application startup.
"""

import asyncio
import logging
from typing import List
from datetime import datetime, timedelta

from db.client import get_supabase_client, async_db
from services.document_service import document_service
from utils.logger import logger


async def get_top_active_projects(limit: int = 10) -> List[str]:
    """
    Get the top N most active projects based on recent activity.
    
    Activity is determined by:
    - Recent document uploads
    - Recent chat messages
    - Recent project access
    
    Args:
        limit: Number of top projects to return (default: 10)
        
    Returns:
        List of project IDs
    """
    try:
        client = get_supabase_client()
        
        # Get projects with recent document activity (last 30 days)
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        result = await async_db(
            lambda: client.table("documents")
            .select("project_id")
            .gte("created_at", cutoff_date)
            .execute()
        )
        
        # Count documents per project
        project_counts = {}
        for doc in result.data:
            project_id = doc["project_id"]
            project_counts[project_id] = project_counts.get(project_id, 0) + 1
        
        # Sort by document count and take top N
        top_projects = sorted(
            project_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        project_ids = [project_id for project_id, _ in top_projects]
        
        logger.info(
            f"Identified {len(project_ids)} active projects for cache warming: "
            f"{project_ids}"
        )
        
        return project_ids
        
    except Exception as e:
        logger.error(f"Error getting top active projects: {e}")
        return []


async def warm_document_metadata_cache(project_ids: List[str] = None) -> bool:
    """
    Warm document metadata cache for specified projects.
    
    If no project_ids provided, warms cache for top 10 active projects.
    
    Args:
        project_ids: List of project IDs to warm cache for (optional)
        
    Returns:
        True if warming completed successfully, False otherwise
    """
    try:
        start_time = datetime.utcnow()
        
        # Get top active projects if not specified
        if project_ids is None:
            project_ids = await get_top_active_projects(limit=10)
        
        if not project_ids:
            logger.warning("No projects to warm cache for")
            return False
        
        logger.info(f"Starting document metadata cache warming for {len(project_ids)} projects")
        
        # Warm cache for each project
        await document_service.warm_cache_for_projects(project_ids)
        
        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            f"Document metadata cache warming completed in {duration:.2f}s "
            f"for {len(project_ids)} projects"
        )
        
        # Verify warming completed within 30 seconds
        if duration > 30:
            logger.warning(
                f"Cache warming took {duration:.2f}s, exceeding 30s target"
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Error warming document metadata cache: {e}")
        return False


async def warm_topics_cache(project_ids: List[str] = None) -> bool:
    """
    Warm topics cache for specified projects.
    
    Preloads topic lists for frequently accessed projects.
    
    Args:
        project_ids: List of project IDs to warm cache for (optional)
        
    Returns:
        True if warming completed successfully, False otherwise
    """
    try:
        from core.redis_manager import get_redis_manager
        import json
        
        redis_manager = get_redis_manager()
        
        # Get top active projects if not specified
        if project_ids is None:
            project_ids = await get_top_active_projects(limit=10)
        
        if not project_ids:
            logger.warning("No projects to warm topics cache for")
            return False
        
        logger.info(f"Starting topics cache warming for {len(project_ids)} projects")
        
        client = get_supabase_client()
        
        for project_id in project_ids:
            try:
                # Fetch topics for project
                result = await async_db(
                    lambda: client.table("documents")
                    .select("topics")
                    .eq("project_id", project_id)
                    .eq("upload_status", "completed")
                    .execute()
                )
                
                # Collect all unique topics
                all_topics = set()
                for doc in result.data:
                    topics = doc.get("topics") or []
                    all_topics.update(topics)
                
                # Cache topics list
                if all_topics:
                    cache_key = f"topics:{project_id}"
                    await redis_manager.set(
                        cache_key,
                        json.dumps(list(all_topics)),
                        ttl=21600  # 6 hours
                    )
                    
                    logger.debug(
                        f"Cached {len(all_topics)} topics for project {project_id}"
                    )
                    
            except Exception as e:
                logger.error(f"Error warming topics cache for project {project_id}: {e}")
        
        logger.info("Topics cache warming completed")
        return True
        
    except Exception as e:
        logger.error(f"Error warming topics cache: {e}")
        return False


async def warm_knowledge_graph_cache(project_ids: List[str] = None) -> bool:
    """
    Warm knowledge graph cache for specified projects.
    
    Preloads knowledge graphs for frequently accessed projects.
    
    Args:
        project_ids: List of project IDs to warm cache for (optional)
        
    Returns:
        True if warming completed successfully, False otherwise
    """
    try:
        from core.redis_manager import get_redis_manager
        import json
        
        redis_manager = get_redis_manager()
        
        # Get top active projects if not specified
        if project_ids is None:
            project_ids = await get_top_active_projects(limit=10)
        
        if not project_ids:
            logger.warning("No projects to warm knowledge graph cache for")
            return False
        
        logger.info(f"Starting knowledge graph cache warming for {len(project_ids)} projects")
        
        client = get_supabase_client()
        
        for project_id in project_ids:
            try:
                # Fetch knowledge graph for project
                result = await async_db(
                    lambda: client.table("knowledge_graphs")
                    .select("*")
                    .eq("project_id", project_id)
                    .execute()
                )
                
                # Cache knowledge graph
                if result.data:
                    cache_key = f"kg:{project_id}"
                    await redis_manager.set(
                        cache_key,
                        json.dumps(result.data[0]),
                        ttl=3600  # 1 hour
                    )
                    
                    logger.debug(f"Cached knowledge graph for project {project_id}")
                    
            except Exception as e:
                logger.error(f"Error warming knowledge graph cache for project {project_id}: {e}")
        
        logger.info("Knowledge graph cache warming completed")
        return True
        
    except Exception as e:
        logger.error(f"Error warming knowledge graph cache: {e}")
        return False


async def warm_all_caches(timeout: int = 30) -> bool:
    """
    Warm all caches on application startup.
    
    Preloads:
    - Document metadata for top 10 active projects
    - Topic lists for top 10 active projects
    - Knowledge graphs for top 10 active projects
    
    Args:
        timeout: Maximum time in seconds for cache warming (default: 30)
        
    Returns:
        True if all warming completed successfully, False otherwise
    """
    try:
        start_time = datetime.utcnow()
        
        logger.info("Starting cache warming on application startup")
        
        # Get top active projects once
        project_ids = await get_top_active_projects(limit=10)
        
        if not project_ids:
            logger.warning("No active projects found for cache warming")
            return False
        
        # Run all warming tasks concurrently with timeout
        warming_tasks = [
            warm_document_metadata_cache(project_ids),
            warm_topics_cache(project_ids),
            warm_knowledge_graph_cache(project_ids)
        ]
        
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*warming_tasks, return_exceptions=True),
                timeout=timeout
            )
            
            # Check results
            success_count = sum(1 for r in results if r is True)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                f"Cache warming completed in {duration:.2f}s: "
                f"{success_count}/{len(warming_tasks)} tasks successful"
            )
            
            return success_count == len(warming_tasks)
            
        except asyncio.TimeoutError:
            logger.error(f"Cache warming timed out after {timeout}s")
            return False
        
    except Exception as e:
        logger.error(f"Error during cache warming: {e}")
        return False


# Convenience function for startup
async def startup_cache_warming():
    """
    Run cache warming on application startup.
    
    This should be called from the FastAPI startup event handler.
    """
    logger.info("Running startup cache warming")
    
    try:
        success = await warm_all_caches(timeout=30)
        
        if success:
            logger.info("Startup cache warming completed successfully")
        else:
            logger.warning("Startup cache warming completed with errors")
            
    except Exception as e:
        logger.error(f"Startup cache warming failed: {e}")
