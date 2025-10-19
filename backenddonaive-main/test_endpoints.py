#!/usr/bin/env python3
"""
Script para probar endpoints localmente
"""
import asyncio
import httpx

async def test_endpoints():
    """Probar endpoints localmente"""
    base_url = "http://localhost:8000"
    
    endpoints = [
        "/",
        "/test-direct", 
        "/test-simple",
        "/health-check",
        "/docs"
    ]
    
    async with httpx.AsyncClient() as client:
        for endpoint in endpoints:
            try:
                response = await client.get(f"{base_url}{endpoint}")
                print(f"✅ {endpoint}: {response.status_code} - {response.json()}")
            except Exception as e:
                print(f"❌ {endpoint}: Error - {e}")

if __name__ == "__main__":
    print("Probando endpoints localmente...")
    asyncio.run(test_endpoints())
