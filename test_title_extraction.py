from services.pexels_service import extract_title_from_url

test_url = "https://www.pexels.com/video/stunning-4k-aerial-view-of-jonkoping-cityscape-35124638/"
video_id = 35124638

title = extract_title_from_url(test_url, video_id)
print(f"URL: {test_url}")
print(f"Extracted Title: {title}")

expected = "Stunning 4k Aerial View Of Jonkoping Cityscape"
if title == expected:
    print("✅ TEST PASSED")
else:
    print(f"❌ TEST FAILED. Expected '{expected}', got '{title}'")
