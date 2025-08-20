#!/usr/bin/env python3
"""
Simple Weather MCP Server for testing multi-server setup.

This server provides mock weather data for testing purposes.
"""

import json
import logging
import random
from typing import Any, Dict, List
from datetime import datetime, timedelta

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherMCPServer:
    """Simple weather MCP server with mock data."""
    
    def __init__(self):
        self.server = Server("weather-mcp")
        self._setup_handlers()
        
        # Mock weather conditions
        self.conditions = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Foggy", "Snowy"]
        
    def _setup_handlers(self):
        """Setup tool and resource handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available weather tools."""
            return [
                Tool(
                    name="get_current_weather",
                    description="Get current weather for a location",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name or location"
                            }
                        },
                        "required": ["location"]
                    }
                ),
                Tool(
                    name="get_forecast",
                    description="Get weather forecast for next 5 days",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name or location"
                            }
                        },
                        "required": ["location"]
                    }
                ),
                Tool(
                    name="get_temperature_trends",
                    description="Get temperature trends for a location",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name or location"
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to analyze",
                                "default": 7
                            }
                        },
                        "required": ["location"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute weather tools."""
            
            if name == "get_current_weather":
                return await self._get_current_weather(arguments)
            elif name == "get_forecast":
                return await self._get_forecast(arguments)
            elif name == "get_temperature_trends":
                return await self._get_temperature_trends(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available weather resources."""
            return [
                Resource(
                    uri="weather://global",
                    name="Global Weather Data",
                    description="Access to global weather information",
                    mimeType="application/json"
                ),
                Resource(
                    uri="weather://cities",
                    name="City Weather Database",
                    description="Weather data for major cities",
                    mimeType="application/json"
                )
            ]
    
    def _generate_weather_data(self, location: str, date: datetime = None) -> Dict:
        """Generate mock weather data for a location."""
        if date is None:
            date = datetime.now()
            
        # Use location hash for consistent random data
        random.seed(hash(location + date.strftime("%Y-%m-%d")))
        
        temp_base = 20 + (hash(location) % 20)  # Base temp 20-40°C
        
        return {
            "location": location,
            "date": date.strftime("%Y-%m-%d"),
            "temperature": temp_base + random.uniform(-5, 5),
            "feels_like": temp_base + random.uniform(-7, 3),
            "humidity": random.randint(30, 90),
            "wind_speed": random.uniform(0, 30),
            "wind_direction": random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"]),
            "condition": random.choice(self.conditions),
            "pressure": random.randint(990, 1030),
            "visibility": random.randint(5, 20),
            "uv_index": random.randint(1, 11)
        }
    
    async def _get_current_weather(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get current weather for a location."""
        try:
            location = arguments.get("location", "Unknown")
            weather = self._generate_weather_data(location)
            
            result = f"Current weather in {location}:\n"
            result += f"Temperature: {weather['temperature']:.1f}°C (feels like {weather['feels_like']:.1f}°C)\n"
            result += f"Condition: {weather['condition']}\n"
            result += f"Humidity: {weather['humidity']}%\n"
            result += f"Wind: {weather['wind_speed']:.1f} km/h {weather['wind_direction']}\n"
            result += f"Pressure: {weather['pressure']} hPa\n"
            result += f"Visibility: {weather['visibility']} km\n"
            result += f"UV Index: {weather['uv_index']}"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error getting weather: {e}")
            return [TextContent(
                type="text",
                text=f"Error getting weather: {str(e)}"
            )]
    
    async def _get_forecast(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get 5-day weather forecast."""
        try:
            location = arguments.get("location", "Unknown")
            
            forecast = []
            for i in range(5):
                date = datetime.now() + timedelta(days=i)
                weather = self._generate_weather_data(location, date)
                forecast.append(weather)
            
            result = f"5-Day Weather Forecast for {location}:\n\n"
            for day_weather in forecast:
                result += f"{day_weather['date']}:\n"
                result += f"  Temperature: {day_weather['temperature']:.1f}°C\n"
                result += f"  Condition: {day_weather['condition']}\n"
                result += f"  Wind: {day_weather['wind_speed']:.1f} km/h\n"
                result += "\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error getting forecast: {e}")
            return [TextContent(
                type="text",
                text=f"Error getting forecast: {str(e)}"
            )]
    
    async def _get_temperature_trends(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get temperature trends analysis."""
        try:
            location = arguments.get("location", "Unknown")
            days = arguments.get("days", 7)
            
            temperatures = []
            dates = []
            
            for i in range(days):
                date = datetime.now() - timedelta(days=days-i-1)
                weather = self._generate_weather_data(location, date)
                temperatures.append(weather['temperature'])
                dates.append(date.strftime("%m/%d"))
            
            avg_temp = sum(temperatures) / len(temperatures)
            max_temp = max(temperatures)
            min_temp = min(temperatures)
            
            # Simple trend analysis
            first_half = sum(temperatures[:days//2]) / (days//2)
            second_half = sum(temperatures[days//2:]) / (days - days//2)
            
            if second_half > first_half + 2:
                trend = "Rising"
            elif second_half < first_half - 2:
                trend = "Falling"
            else:
                trend = "Stable"
            
            result = f"Temperature Trends for {location} (last {days} days):\n\n"
            result += f"Average: {avg_temp:.1f}°C\n"
            result += f"Maximum: {max_temp:.1f}°C\n"
            result += f"Minimum: {min_temp:.1f}°C\n"
            result += f"Trend: {trend}\n\n"
            result += "Daily temperatures:\n"
            
            for date, temp in zip(dates, temperatures):
                bar_length = int((temp - min_temp) / (max_temp - min_temp) * 20) if max_temp != min_temp else 10
                bar = "█" * bar_length
                result += f"{date}: {temp:5.1f}°C {bar}\n"
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error getting temperature trends: {e}")
            return [TextContent(
                type="text",
                text=f"Error getting temperature trends: {str(e)}"
            )]
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Weather MCP Server started")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


if __name__ == "__main__":
    server = WeatherMCPServer()
    
    import asyncio
    asyncio.run(server.run())