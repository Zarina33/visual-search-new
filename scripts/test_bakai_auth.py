#!/usr/bin/env python3
"""
Скрипт для тестирования различных методов авторизации BakaiMarket API.
"""
import asyncio
import httpx
from app.config import settings


async def test_auth_method_1():
    """Test with X-Access-Key and X-Secret-Key headers."""
    print("\n" + "=" * 70)
    print("🔐 ТЕСТ 1: X-Access-Key и X-Secret-Key в headers")
    print("=" * 70)
    
    headers = {
        "X-Access-Key": settings.bakai_cdn_access_key,
        "X-Secret-Key": settings.bakai_cdn_secret_key,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{settings.bakai_cdn_api_url}/products",
                headers=headers,
                params={"limit": 1}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


async def test_auth_method_2():
    """Test with Authorization: Bearer token."""
    print("\n" + "=" * 70)
    print("🔐 ТЕСТ 2: Authorization Bearer token")
    print("=" * 70)
    
    headers = {
        "Authorization": f"Bearer {settings.bakai_cdn_access_key}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{settings.bakai_cdn_api_url}/products",
                headers=headers,
                params={"limit": 1}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


async def test_auth_method_3():
    """Test with Basic Auth."""
    print("\n" + "=" * 70)
    print("🔐 ТЕСТ 3: Basic Auth (access_key:secret_key)")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{settings.bakai_cdn_api_url}/products",
                auth=(settings.bakai_cdn_access_key, settings.bakai_cdn_secret_key),
                params={"limit": 1}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


async def test_auth_method_4():
    """Test with query parameters."""
    print("\n" + "=" * 70)
    print("🔐 ТЕСТ 4: Query parameters (access_key & secret_key)")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{settings.bakai_cdn_api_url}/products",
                params={
                    "limit": 1,
                    "access_key": settings.bakai_cdn_access_key,
                    "secret_key": settings.bakai_cdn_secret_key
                }
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


async def test_auth_method_5():
    """Test with API-Key header."""
    print("\n" + "=" * 70)
    print("🔐 ТЕСТ 5: API-Key header")
    print("=" * 70)
    
    headers = {
        "API-Key": settings.bakai_cdn_access_key,
        "API-Secret": settings.bakai_cdn_secret_key,
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{settings.bakai_cdn_api_url}/products",
                headers=headers,
                params={"limit": 1}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


async def test_root_endpoint():
    """Test root endpoint without auth."""
    print("\n" + "=" * 70)
    print("🔍 ТЕСТ: Проверка root endpoint (без авторизации)")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(settings.bakai_cdn_api_url)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")


async def test_different_endpoints():
    """Test different possible endpoints."""
    print("\n" + "=" * 70)
    print("🔍 ТЕСТ: Проверка различных endpoints")
    print("=" * 70)
    
    endpoints = [
        "/products",
        "/api/products",
        "/v1/products",
        "/api/v1/products",
        "/items",
        "/catalog",
    ]
    
    headers = {
        "X-Access-Key": settings.bakai_cdn_access_key,
        "X-Secret-Key": settings.bakai_cdn_secret_key,
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for endpoint in endpoints:
            try:
                url = f"{settings.bakai_cdn_api_url}{endpoint}"
                response = await client.get(url, headers=headers, params={"limit": 1})
                print(f"\n{endpoint}: {response.status_code}")
                if response.status_code != 403 and response.status_code != 404:
                    print(f"   Response: {response.text[:200]}")
            except Exception as e:
                print(f"\n{endpoint}: ❌ {str(e)[:100]}")


async def main():
    """Run all auth tests."""
    print("\n" + "=" * 70)
    print("  🔐 ТЕСТИРОВАНИЕ МЕТОДОВ АВТОРИЗАЦИИ")
    print("=" * 70)
    print(f"\nAPI URL: {settings.bakai_cdn_api_url}")
    print(f"Access Key: {settings.bakai_cdn_access_key[:10]}...")
    print(f"Secret Key: {settings.bakai_cdn_secret_key[:10]}...")
    
    # Test root
    await test_root_endpoint()
    
    # Test different endpoints
    await test_different_endpoints()
    
    # Test auth methods
    methods = [
        test_auth_method_1,
        test_auth_method_2,
        test_auth_method_3,
        test_auth_method_4,
        test_auth_method_5,
    ]
    
    for method in methods:
        success = await method()
        if success:
            print("\n✅ ЭТОТ МЕТОД РАБОТАЕТ!")
            break
    
    print("\n" + "=" * 70)
    print("📝 РЕКОМЕНДАЦИЯ:")
    print("=" * 70)
    print("\nСвяжитесь с командой BakaiMarket и уточните:")
    print("1. Правильный endpoint для получения товаров")
    print("2. Формат авторизации (какие headers использовать)")
    print("3. Документацию API")
    print("\nВозможно нужно:")
    print("- Другой URL (например /api/v1/products)")
    print("- Другой формат headers")
    print("- Дополнительные параметры")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

