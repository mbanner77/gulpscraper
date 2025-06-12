async def scrape_gulp(pages: range = PAGE_RANGE) -> List[Dict]:
    """Run the GULP scraper and return the projects."""
    global is_scraping, last_scrape_time, project_manager, email_service, email_notification_enabled, email_recipient
    
    if is_scraping:
        print("Scrape already in progress, skipping...")
        return []
    
    is_scraping = True
    all_projects: List[Dict] = []
    network_lines: List[str] = []
    
    try:
        print(f"\n[SCRAPER] Starting GULP scraper at {datetime.datetime.now().isoformat()}")
        print(f"[SCRAPER] Using real scraper: {USE_REAL_SCRAPER}")
        print(f"[SCRAPER] Running in cloud environment: {IS_CLOUD_ENV}")
        
        # Erstelle Debug-Verzeichnisse, falls sie nicht existieren
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        DEBUG_DIR.mkdir(exist_ok=True, parents=True)
        
        # Wenn USE_REAL_SCRAPER=False ist, laden wir Dummy-Daten
        if not USE_REAL_SCRAPER:
            print("[SCRAPER] USE_REAL_SCRAPER=False, lade Dummy-Daten")
            
            # Erstelle ein einfaches Dummy-Projekt
            dummy_projects = [
                {
                    "id": f"dummy-1-{datetime.datetime.now().strftime('%Y%m%d%H%M')}",
                    "title": "Dummy Projekt 1",
                    "description": "Dies ist ein automatisch erstelltes Dummy-Projekt.",
                    "companyName": "Dummy GmbH",
                    "location": "Berlin",
                    "isRemoteWorkPossible": True,
                    "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
                    "originalPublicationDate": datetime.datetime.now().isoformat(),
                    "url": "https://www.gulp.de/"
                },
                {
                    "id": f"dummy-2-{datetime.datetime.now().strftime('%Y%m%d%H%M')}",
                    "title": "Dummy Projekt 2",
                    "description": "Ein weiteres automatisch erstelltes Dummy-Projekt.",
                    "companyName": "Test AG",
                    "location": "München",
                    "isRemoteWorkPossible": True,
                    "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
                    "originalPublicationDate": datetime.datetime.now().isoformat(),
                    "url": "https://www.gulp.de/"
                }
            ]
            
            # Speichere die Dummy-Projekte
            OUTPUT_JSON.write_text(
                json.dumps(dummy_projects, indent=2, ensure_ascii=False), 
                encoding="utf-8"
            )
            print(f"[SCRAPER] {len(dummy_projects)} Dummy-Projekte erstellt")
            
            # Aktualisiere den Zeitstempel des letzten Scans
            last_scrape_time = datetime.datetime.now().isoformat()
            print(f"[SCRAPER] Updated last_scrape_time to {last_scrape_time}")
            
            # Verarbeite die Dummy-Projekte
            unique_projects, new_projects = project_manager.process_projects(dummy_projects)
            
            # Sende E-Mail-Benachrichtigung, wenn aktiviert und neue Projekte gefunden wurden
            if email_notification_enabled and email_recipient and new_projects:
                try:
                    print(f"\n[SCRAPER] Versuche E-Mail-Benachrichtigung zu senden...")
                    if email_service:
                        success = email_service.send_new_projects_notification(
                            recipient=email_recipient,
                            new_projects=new_projects,
                            scan_time=datetime.datetime.now()
                        )
                        print(f"[SCRAPER] E-Mail-Versand Ergebnis: {'Erfolgreich' if success else 'Fehlgeschlagen'}")
                except Exception as e:
                    print(f"[SCRAPER] Error sending email notification: {str(e)}")
            
            is_scraping = False
            return dummy_projects
        
        # Wenn USE_REAL_SCRAPER=True, verwenden wir Playwright für echtes Scraping
        print("\n[SCRAPER] Starting real scraper with Playwright...")
        
        # Playwright-Konfiguration
        launch_options = {
            "headless": True,
        }
        
        # Spezielle Konfiguration für Render
        if IS_CLOUD_ENV:
            print(f"[RENDER DEBUG] Verwende spezielle Browser-Konfiguration für Render")
            launch_options["chromium_sandbox"] = False
            launch_options["timeout"] = 60000  # Erhöhtes Timeout für Render
            # Weitere Render-spezifische Optionen
            launch_options["args"] = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--single-process",
                "--disable-gpu"
            ]
        
        print(f"[SCRAPER] Launching browser with options: {launch_options}")
        
        # Verwende einen try-except-Block für die Playwright-Initialisierung
        try:
            async with async_playwright() as pw:
                print("[SCRAPER] Playwright erfolgreich initialisiert")
                
                try:
                    # Browser starten
                    print("[SCRAPER] Starte Browser...")
                    browser = await pw.chromium.launch(**launch_options)
                    print("[SCRAPER] Browser erfolgreich gestartet")
                    
                    try:
                        context = await browser.new_context(
                            user_agent=USER_AGENT, 
                            viewport={"width": 1280, "height": 900}
                        )
                        print("[SCRAPER] Browser-Kontext erstellt")
                        
                        try:
                            page = await context.new_page()
                            print("[SCRAPER] Neue Seite geöffnet")
                            
                            # Netzwerkanfragen protokollieren
                            page.on("response", lambda resp: network_lines.append(
                                f"{resp.status} {resp.request.method} {resp.url} [{resp.headers.get('content-type', '')}]"))
                            
                            # Durchlaufe alle Seiten
                            for page_idx in pages:
                                print(f"→ Page {page_idx}: {START_URL_TEMPLATE.format(page=page_idx)}")
                                captured: List[Tuple[str, Any]] = []
                                
                                def handle_response(resp):
                                    if API_RE.search(resp.url) and "application/json" in resp.headers.get("content-type", ""):
                                        async def _grab():
                                            try:
                                                captured.append((resp.url, await resp.json()))
                                            except Exception:
                                                pass
                                        asyncio.create_task(_grab())
                                
                                page.on("response", handle_response)
                                
                                try:
                                    await page.goto(
                                        START_URL_TEMPLATE.format(page=page_idx), 
                                        timeout=TIMEOUT_MS, 
                                        wait_until="domcontentloaded"
                                    )
                                except PwTimeout:
                                    print("   ! DOMContentLoaded Timeout – skipping page")
                                    continue
                                
                                # Scrolle durch die Seite
                                for _ in range(SCROLL_STEPS):
                                    await page.mouse.wheel(0, 4000)
                                    await asyncio.sleep(SCROLL_PAUSE)
                                await asyncio.sleep(COLLECT_SECS)
                                
                                # Verarbeite die API-Antworten
                                if captured:
                                    feed_url, api_json = captured[0]
                                    (DEBUG_DIR / f"api_page{page_idx}.json").write_text(
                                        json.dumps(api_json, indent=2, ensure_ascii=False), 
                                        encoding="utf-8"
                                    )
                                else:
                                    feed_url, api_json = "n/a", {}
                                
                                # Extrahiere Projekte aus der API-Antwort
                                projects: List[Dict] = []
                                if isinstance(api_json, dict):
                                    for key in ("content", "data", "items", "projects", "results"):
                                        if isinstance(api_json.get(key), list):
                                            projects = api_json[key]
                                            break
                                if not projects:
                                    projects = find_projects_recursive(api_json)
                                
                                print(f"   {len(projects)} projects found (source: {feed_url})")
                                all_projects.extend(projects)
                            
                            # Schließe Browser-Ressourcen
                            await page.close()
                            await context.close()
                            await browser.close()
                            print("[SCRAPER] Browser-Ressourcen erfolgreich freigegeben")
                            
                        except Exception as page_error:
                            print(f"[SCRAPER] Error creating page: {str(page_error)}")
                            if context:
                                await context.close()
                            if browser:
                                await browser.close()
                    
                    except Exception as context_error:
                        print(f"[SCRAPER] Error creating context: {str(context_error)}")
                        if browser:
                            await browser.close()
                
                except Exception as browser_error:
                    print(f"[SCRAPER] Error launching browser: {str(browser_error)}")
        
        except Exception as pw_error:
            print(f"[SCRAPER] Error initializing Playwright: {str(pw_error)}")
            import traceback
            print(f"[SCRAPER] Traceback: {traceback.format_exc()}")
        
        # Verarbeite die gescrapten Projekte
        if all_projects:
            # Speichere die Projekte
            OUTPUT_JSON.write_text(
                json.dumps(all_projects, indent=2, ensure_ascii=False), 
                encoding="utf-8"
            )
            NETWORK_LOG.write_text("\n".join(network_lines), encoding="utf-8")
            
            # Verarbeite die Projekte (Duplikaterkennung und neue Projekte identifizieren)
            unique_projects, new_projects = project_manager.process_projects(all_projects)
            
            print(f"✓ Scraping completed at {datetime.datetime.now().isoformat()}")
            print(f"  → {len(unique_projects)} unique projects saved to {OUTPUT_JSON}")
            print(f"  → {len(new_projects)} new projects found")
            
            # Aktualisiere den Zeitstempel des letzten Scans
            last_scrape_time = datetime.datetime.now().isoformat()
            
            # Sende E-Mail-Benachrichtigung, wenn aktiviert und neue Projekte gefunden wurden
            if email_notification_enabled and email_recipient and new_projects:
                print(f"\n[SCRAPER] Versuche E-Mail-Benachrichtigung zu senden...")
                if not email_service:
                    print(f"[SCRAPER] E-Mail-Service ist nicht initialisiert!")
                else:
                    print(f"[SCRAPER] E-Mail-Service Status: {email_service.get_config_status().get('is_configured')}")
                    try:
                        success = email_service.send_new_projects_notification(
                            recipient=email_recipient,
                            new_projects=new_projects,
                            scan_time=datetime.datetime.now()
                        )
                        print(f"[SCRAPER] E-Mail-Versand Ergebnis: {'Erfolgreich' if success else 'Fehlgeschlagen'}")
                    except Exception as e:
                        print(f"[SCRAPER] Error sending email notification: {str(e)}")
            
            return unique_projects
        
        # Wenn keine Projekte gefunden wurden und wir auf Render sind, verwenden wir Dummy-Daten als Fallback
        elif IS_CLOUD_ENV:
            print("[RENDER DEBUG] No projects found with real scraper, falling back to dummy data")
            
            # Erstelle ein einfaches Dummy-Projekt als Fallback
            dummy_projects = [
                {
                    "id": f"fallback-1-{datetime.datetime.now().strftime('%Y%m%d%H%M')}",
                    "title": "Fallback Projekt 1",
                    "description": "Dies ist ein Fallback-Projekt für Render, da der echte Scraper keine Projekte gefunden hat.",
                    "companyName": "Fallback GmbH",
                    "location": "Berlin",
                    "isRemoteWorkPossible": True,
                    "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
                    "originalPublicationDate": datetime.datetime.now().isoformat(),
                    "url": "https://www.gulp.de/"
                }
            ]
            
            # Speichere die Dummy-Projekte
            OUTPUT_JSON.write_text(
                json.dumps(dummy_projects, indent=2, ensure_ascii=False), 
                encoding="utf-8"
            )
            print(f"[RENDER DEBUG] Created fallback dummy data with {len(dummy_projects)} projects")
            
            # Aktualisiere den Zeitstempel des letzten Scans
            last_scrape_time = datetime.datetime.now().isoformat()
            
            # Verarbeite die Dummy-Projekte
            unique_projects, new_projects = project_manager.process_projects(dummy_projects)
            
            return unique_projects
        
        # Wenn keine Projekte gefunden wurden und wir nicht auf Render sind, geben wir eine leere Liste zurück
        else:
            print("[SCRAPER] No projects found")
            return []
    
    except Exception as e:
        print(f"\n[SCRAPER] Error during scraping: {str(e)}")
        import traceback
        print(f"[SCRAPER] Traceback: {traceback.format_exc()}")
        
        # Bei Fehlern auf Render versuchen wir, zumindest Dummy-Daten zu laden
        if IS_CLOUD_ENV:
            print("[RENDER DEBUG] Error with real scraper on Render, creating emergency dummy data")
            
            try:
                # Erstelle ein einfaches Dummy-Projekt für den Notfall
                emergency_projects = [
                    {
                        "id": f"emergency-{datetime.datetime.now().strftime('%Y%m%d%H%M')}",
                        "title": "Notfall-Projekt",
                        "description": "Dieses Projekt wurde erstellt, weil beim Scraping ein Fehler aufgetreten ist.",
                        "companyName": "Notfall GmbH",
                        "location": "Berlin",
                        "isRemoteWorkPossible": True,
                        "publicationDate": datetime.datetime.now().strftime("%d.%m.%Y"),
                        "originalPublicationDate": datetime.datetime.now().isoformat(),
                        "url": "https://www.gulp.de/"
                    }
                ]
                
                # Speichere die Notfall-Projekte
                DATA_DIR.mkdir(exist_ok=True, parents=True)
                OUTPUT_JSON.write_text(
                    json.dumps(emergency_projects, indent=2, ensure_ascii=False), 
                    encoding="utf-8"
                )
                print(f"[RENDER DEBUG] Created emergency data file with {len(emergency_projects)} projects")
                
                # Aktualisiere den Zeitstempel des letzten Scans
                last_scrape_time = datetime.datetime.now().isoformat()
                
                # Verarbeite die Notfall-Projekte
                unique_projects, _ = project_manager.process_projects(emergency_projects)
                
                return unique_projects
            
            except Exception as fallback_error:
                print(f"[RENDER DEBUG] Fallback to emergency data also failed: {str(fallback_error)}")
                return []
        
        return []
    
    finally:
        # Stelle sicher, dass is_scraping zurückgesetzt wird, egal was passiert
        is_scraping = False
        print("[SCRAPER] Scraper finished, is_scraping set to False")
