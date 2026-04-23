Object.assign(MapApp.prototype, {
    ensureCorridorTimerLabelLayer() {
      if (!this.map) {
        return;
      }
      if (!this.corridorScheduleZoomBound) {
        this.corridorScheduleZoomBound = true;
        this.map.on("zoom", () => {
          this.updateCorridorTimedLabels(this.lastSimTime_s);
        });
      }
      const empty = { type: "FeatureCollection", features: [] };
      const sourceId = "corridor-timer-labels";
      const layerId = "corridor-timer-labels";
      const markerLayerId = "corridor-timer-markers";
      const badgeLayerId = "corridor-timer-badges";
      if (!this.map.getSource(sourceId)) {
        try {
          this.map.addSource(sourceId, { type: "geojson", data: empty });
        } catch (_err) {
          return;
        }
      }
      const beforeId = this.map.getLayer("traffic-glow") ? "traffic-glow" : undefined;
      if (!this.map.getLayer(markerLayerId)) {
        try {
          this.map.addLayer(
            {
              id: markerLayerId,
              type: "circle",
              source: sourceId,
              minzoom: 6,
              paint: {
                "circle-radius": [
                  "interpolate",
                  ["linear"],
                  ["zoom"],
                  6,
                  4 * UI_SCALE,
                  14,
                  7 * UI_SCALE,
                ],
                "circle-color": ["coalesce", ["get", "markerColor"], "#94a3b8"],
                "circle-stroke-color": "rgba(12, 18, 26, 0.6)",
                "circle-stroke-width": 1.2,
                "circle-opacity": 0.95,
              },
            },
            beforeId,
          );
        } catch (_err) {
          // ignore
        }
      }
      if (!this.map.getLayer(badgeLayerId)) {
        try {
          this.map.addLayer(
            {
              id: badgeLayerId,
              type: "symbol",
              source: sourceId,
              minzoom: 6,
              layout: {
                "text-field": ["coalesce", ["get", "badge"], ""],
                "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
                "text-size": [
                  "interpolate",
                  ["linear"],
                  ["zoom"],
                  6,
                  8 * UI_SCALE,
                  14,
                  13 * UI_SCALE,
                ],
                "text-allow-overlap": true,
                "text-ignore-placement": true,
                "text-padding": 0,
                "text-anchor": "center",
              },
              paint: {
                "text-color": "#f8fafc",
                "text-halo-color": "rgba(12, 18, 26, 0.85)",
                "text-halo-width": 1.2,
                "text-halo-blur": 0.5,
              },
            },
            beforeId,
          );
        } catch (_err) {
          // ignore
        }
      }
      if (this.map.getLayer(layerId)) {
        return;
      }
      try {
        this.map.addLayer(
          {
            id: layerId,
            type: "symbol",
            source: sourceId,
            minzoom: 6,
            layout: {
              "text-field": ["get", "label"],
              "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
              "text-size": [
                "interpolate",
                ["linear"],
                ["zoom"],
                6,
                11 * UI_SCALE,
                14,
                15 * UI_SCALE,
              ],
              "symbol-sort-key": ["-", ["get", "remaining"]],
              "text-allow-overlap": true,
              "text-ignore-placement": true,
              "text-padding": 1,
              "text-variable-anchor": ["top", "bottom", "left", "right"],
              "text-radial-offset": 0.7,
              "text-justify": "auto",
              "text-keep-upright": true,
              "text-pitch-alignment": "map",
              "text-rotation-alignment": "map",
            },
            paint: {
              "text-color": "#f8fafc",
              "text-halo-color": "rgba(10, 15, 22, 0.9)",
              "text-halo-width": 1.6,
              "text-halo-blur": 0.6,
            },
          },
          beforeId,
        );
      } catch (_err) {
        // ignore
      }
    },
    resolveNodeAltitude(name) {
      const corridor = this.corridorPointLookup.get(name);
      if (corridor && Number.isFinite(corridor.altitude_m)) {
        return corridor.altitude_m;
      }
      const port = this.vertiportPointLookup.get(name);
      if (port && Number.isFinite(port.altitude_m)) {
        return port.altitude_m;
      }
      return 0;
    },

    computeUeMeters(lat, lon, altitude_m) {
      const [absX, absY, absZ] = this.airsimConverter.geodeticToUe(lat, lon, altitude_m);
      const [chx, chy, chz] = this.airsimConverter.cityHall;
      return [(absX - chx) / 100.0, (absY - chy) / 100.0, (absZ - chz) / 100.0];
    },

    resolveNodeGeodetic(name) {
      const resource = this.vertiportResourceLookup.get(name);
      if (resource) {
        const lat = Number(resource.lat);
        const lon = Number(resource.lon);
        const alt =
          resource.alt_m != null && Number.isFinite(resource.alt_m)
            ? Number(resource.alt_m)
            : this.resolveNodeAltitude(name);
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
          return {
            lat,
            lon,
            altitude_m: alt,
            ue_x: resource.ue_x,
            ue_y: resource.ue_y,
            ue_z: resource.ue_z,
          };
        }
      }
      const entry = this.routeNodeLookup.get(name);
      if (!entry) {
        return null;
      }
      const [lon, lat] = entry.coord;
      const altitude = this.resolveNodeAltitude(name);
      return { lat, lon, altitude_m: altitude };
    },

    buildPlanPoints(path) {
      const points = [];
      path.forEach((name) => {
        const geo = this.resolveNodeGeodetic(name);
        if (!geo) {
          return;
        }
        const { lat, lon, altitude_m } = geo;
        const [n, e, d] = this.airsimConverter.wgs84ToAirsimNed(lat, lon, altitude_m);
        let ueX = geo.ue_x;
        let ueY = geo.ue_y;
        let ueZ = geo.ue_z;
        if (
          !Number.isFinite(ueX) ||
          !Number.isFinite(ueY) ||
          !Number.isFinite(ueZ)
        ) {
          [ueX, ueY, ueZ] = this.computeUeMeters(lat, lon, altitude_m);
        }
        points.push({
          name,
          lat,
          lon,
          altitude_m,
          ue_x: ueX,
          ue_y: ueY,
          ue_z: ueZ,
          n,
          e,
          d,
        });
      });
      return points;
    },

    printPlanRoute(planPoints) {
      if (!planPoints || !planPoints.length) {
        console.warn("[Flight Plan] empty.");
        return;
      }
      const format = (value, digits) =>
        Number.isFinite(value) ? Number(value).toFixed(digits) : "";
      console.warn("[Flight Plan]");
      planPoints.forEach((point) => {
        const lat = format(point.lat, 6);
        const lon = format(point.lon, 6);
        const alt = format(point.altitude_m, 3);
        const ux = format(point.ue_x, 3);
        const uy = format(point.ue_y, 3);
        const uz = format(point.ue_z, 3);
        console.warn(`${point.name} : ${lat} : ${lon} : ${alt} : ${ux} : ${uy} : ${uz}`);
      });
    },

    captureHomeView() {
      if (!this.map) {
        return;
      }
      const center = this.map.getCenter();
      this.homeView = {
        center: [center.lng, center.lat],
        zoom: this.map.getZoom(),
        bearing: this.map.getBearing(),
        pitch: this.map.getPitch(),
      };
    },

    resetView() {
      if (!this.map) {
        return;
      }
      if (this.centerOnTelemetry()) {
        return;
      }
      if (!this.homeView) {
        return;
      }
      this.map.easeTo({
        center: this.homeView.center,
        zoom: this.homeView.zoom,
        bearing: this.homeView.bearing,
        pitch: this.homeView.pitch,
        duration: 400,
      });
    },

    centerOnTelemetry() {
      if (!this.map || !this.telemetryPosition) {
        return false;
      }
      const zoom = Math.max(this.map.getZoom(), 15);
      this.map.easeTo({
        center: this.telemetryPosition,
        zoom,
        duration: 500,
      });
      return true;
    },

    togglePanel(name) {
      const panel = this.panels[name];
      if (!panel) {
        return;
      }
      const isVisible = panel.classList.contains("is-visible");
      if (name === "corridor" && this.isPlaying && !isVisible) {
        this.addStatusMessage({
          text: this.t("status.edit_disabled"),
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      if (isVisible) {
        this.hidePanel(name);
      } else {
        this.showPanel(name);
      }
    },

    showPanel(name) {
      Object.entries(this.panels).forEach(([key, panel]) => {
        const isTarget = key === name;
        if (panel) {
          panel.classList.toggle("is-visible", isTarget);
          panel.setAttribute("aria-hidden", isTarget ? "false" : "true");
        }
        this.setActionButtonActive(key, isTarget);
      });
      this.setEditMode(this.editMode);
      if (this.syncBaseToggleState) {
        this.syncBaseToggleState();
      }
      if (this.tutorialMode === "guided" && typeof this.refreshTutorialLayout === "function") {
        this.refreshTutorialLayout();
      }
    },

    hidePanel(name) {
      const panel = this.panels[name];
      if (!panel) {
        return;
      }
      panel.classList.remove("is-visible");
      panel.setAttribute("aria-hidden", "true");
      this.setActionButtonActive(name, false);
      if (name === "corridor") {
        this.setEditMode(null);
      }
      if (this.syncBaseToggleState) {
        this.syncBaseToggleState();
      }
      if (this.tutorialMode === "guided" && typeof this.refreshTutorialLayout === "function") {
        this.refreshTutorialLayout();
      }
    },

    isSimulationRunning() {
      return Boolean(this.isPlaying);
    },

    syncEditModeAvailability() {
      const blocked = this.isSimulationRunning();
      if (this.editModeButtons) {
        Object.values(this.editModeButtons).forEach((button) => {
          if (button) {
            button.disabled = blocked;
          }
        });
      }
      if (blocked && this.editMode) {
        this.setEditMode(null);
      }
    },

    toggleEditMode(mode) {
      const next = this.editMode === mode ? null : mode;
      if (next && this.isSimulationRunning()) {
        this.addStatusMessage({
          text: this.t("status.edit_disabled"),
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      this.setEditMode(next);
    },

    setEditMode(mode) {
      if (mode && this.isSimulationRunning()) {
        return;
      }
      this.editMode = mode || null;
      const corridorVisible =
        this.panels.corridor && this.panels.corridor.classList.contains("is-visible");
      const showAirspace = corridorVisible && this.editMode === "airspace";
      const showVertiport = corridorVisible && this.editMode === "vertiport";
      const showBaseStation = corridorVisible && this.editMode === "basestation";
      const applyPanel = (panel, visible) => {
        if (!panel) {
          return;
        }
        panel.classList.toggle("is-visible", visible);
        panel.setAttribute("aria-hidden", visible ? "false" : "true");
      };
      applyPanel(this.editToolPanels.airspace, showAirspace);
      applyPanel(this.editToolPanels.vertiport, showVertiport);
      if (this.editModeButtons.airspace) {
        this.editModeButtons.airspace.classList.toggle("is-active", showAirspace);
      }
      if (this.editModeButtons.vertiport) {
        this.editModeButtons.vertiport.classList.toggle("is-active", showVertiport);
      }
      if (this.editModeButtons.basestation) {
        this.editModeButtons.basestation.classList.toggle("is-active", showBaseStation);
      }
      if (this.activeEditTools) {
        this.activeEditTools.airspace = showAirspace ? "airspace-node" : null;
        this.activeEditTools.vertiport = showVertiport ? "vertiport-node" : null;
        this.activeEditTools.basestation = showBaseStation ? "basestation-node" : null;
      }
      if (this.mapContainer) {
        this.mapContainer.classList.toggle(
          "is-editing",
          showAirspace || showVertiport || showBaseStation,
        );
      }
      if (this.updateEditModeMapStyle) {
        this.updateEditModeMapStyle(showAirspace || showVertiport || showBaseStation);
      }
      if (showVertiport && this.ensureEditableFile) {
        void this.ensureEditableFile("vertiport");
      }
      if (showAirspace && this.ensureEditableFile) {
        void this.ensureEditableFile("corridor");
      }
      if (showBaseStation && this.ensureEditableFile) {
        void this.ensureEditableFile("basestation");
      }
      if (this.reorderPlanLayers) {
        this.reorderPlanLayers();
      }
      this.refreshVertiportEditTools();
      this.refreshAirspaceEditTools();
      if (this.refreshBaseStationEditTools) {
        this.refreshBaseStationEditTools();
      }
    },

    getVertiportEditTool() {
      return this.activeEditTools ? this.activeEditTools.vertiport : null;
    },

    isVertiportEditMode() {
      return this.editMode === "vertiport";
    },

    isVertiportNodeToolActive() {
      return this.isVertiportEditMode() && this.getVertiportEditTool() === "vertiport-node";
    },

    refreshVertiportEditTools() {
      const inEditMode = this.isVertiportEditMode();
      if (!inEditMode) {
        this.vertiportEditMovingId = null;
        this.vertiportEditMovingName = null;
        this.clearVertiportEditHighlight();
        this.clearVertiportLinking();
        this.hideVertiportEditPopup();
        this.hideVertiportEditCoordLabel();
        if (this.map) {
          this.map.getCanvas().style.cursor = "";
        }
      }
      if (!inEditMode || !this.isVertiportNodeToolActive()) {
        this.vertiportEditMovingName = null;
        this.clearVertiportEditHighlight();
        this.clearVertiportLinking();
        this.hideVertiportEditGhost();
        this.hideVertiportEditCoordLabel();
        if (this.map) {
          this.map.getCanvas().style.cursor = "";
        }
        return;
      }
      this.ensureVertiportEditGhost();
      if (this.vertiportEditGhostLngLat) {
        this.showVertiportEditGhost(this.vertiportEditGhostLngLat);
      }
    },

    getAirspaceEditTool() {
      return this.activeEditTools ? this.activeEditTools.airspace : null;
    },

    isAirspaceEditMode() {
      return this.editMode === "airspace";
    },

    isAirspaceNodeToolActive() {
      return this.isAirspaceEditMode() && this.getAirspaceEditTool() === "airspace-node";
    },

    refreshAirspaceEditTools() {
      const inEditMode = this.isAirspaceEditMode();
      if (!inEditMode) {
        this.corridorEditMovingId = null;
        this.corridorEditMovingName = null;
        this.clearCorridorEditHighlight();
        this.clearCorridorLinking();
        this.hideCorridorEditPopup();
        this.hideCorridorEditCoordLabel();
        this.hideCorridorEditGhost();
        if (this.map) {
          this.map.getCanvas().style.cursor = "";
        }
        return;
      }
      if (!this.isAirspaceNodeToolActive()) {
        this.corridorEditMovingName = null;
        this.clearCorridorEditHighlight();
        this.clearCorridorLinking();
        this.hideCorridorEditPopup();
        this.hideCorridorEditCoordLabel();
        this.hideCorridorEditGhost();
        if (this.map) {
          this.map.getCanvas().style.cursor = "";
        }
        return;
      }
      this.ensureCorridorEditGhost();
      if (this.corridorEditGhostLngLat) {
        this.showCorridorEditGhost(this.corridorEditGhostLngLat);
      }
    },

    getBaseStationEditTool() {
      return this.activeEditTools ? this.activeEditTools.basestation : null;
    },

    isBaseStationEditMode() {
      return this.editMode === "basestation";
    },

    isBaseStationNodeToolActive() {
      return this.isBaseStationEditMode() && this.getBaseStationEditTool() === "basestation-node";
    },

    refreshBaseStationEditTools() {
      if (!this.map) {
        return;
      }
      const inEditMode = this.isBaseStationEditMode();
      if (!inEditMode) {
        this.baseStationEditMovingId = null;
        this.baseStationEditMovingName = null;
        this.clearBaseStationEditHighlight();
        this.hideBaseStationEditPopup();
        this.map.getCanvas().style.cursor = "";
        return;
      }
      if (!this.isBaseStationNodeToolActive()) {
        this.baseStationEditMovingId = null;
        this.baseStationEditMovingName = null;
        this.clearBaseStationEditHighlight();
        this.hideBaseStationEditPopup();
        this.map.getCanvas().style.cursor = "";
        return;
      }
      this.ensureBaseStationEditLayer();
      this.map.getCanvas().style.cursor = "crosshair";
    },

    setActionButtonActive(action, isActive) {
      this.actionButtons.forEach((button) => {
        if (button.dataset.action === action) {
          button.classList.toggle("is-active", isActive);
        }
      });
    },

    setTheme(theme) {
      if (theme === this.currentTheme) {
        return;
      }
      this.currentTheme = theme;
      this.applyTheme(theme);
    },

    applyTheme(theme) {
      const isDark = theme === "dark";
      this.mapContainer.classList.toggle("theme-dark", isDark);
      this.themeButtons.forEach((button) => {
        button.classList.toggle("is-active", button.dataset.theme === theme);
      });
      this.updateMapTheme(theme);
      this.updateEditModeMapStyle(
        this.editMode === "airspace" ||
          this.editMode === "vertiport" ||
          this.editMode === "basestation",
      );
      this.updateCorridorTheme(theme);
    },

    getCorridorColor(theme) {
      return "#2f6bff";
    },

    applyMapPalette(palette) {
      if (!this.map) {
        return;
      }
      const setPaint = (layer, prop, value) => {
        if (!this.map || !this.map.getLayer(layer)) {
          return;
        }
        try {
          this.map.setPaintProperty(layer, prop, value);
        } catch (error) {
          return;
        }
      };
      setPaint("background", "background-color", palette.background);
      setPaint("landcover", "fill-color", palette.landcover);
      setPaint("landuse", "fill-color", palette.landuse);
      setPaint("park", "fill-color", palette.park);
      setPaint("water", "fill-color", palette.water);
      setPaint("waterway", "line-color", palette.waterway);
      setPaint("boundary", "line-color", palette.boundary);
      setPaint("transportation", "line-color", palette.transportation);
      setPaint("building", "fill-color", palette.building);
    },

    setBaseMapVisibility(theme) {
      if (!this.map) {
        return;
      }
      const useReal = theme === "real";
      const setVisibility = (layer, visible) => {
        if (!this.map || !this.map.getLayer || !this.map.getLayer(layer)) {
          return;
        }
        try {
          this.map.setLayoutProperty(layer, "visibility", visible ? "visible" : "none");
        } catch (error) {
          return;
        }
      };
      setVisibility(REAL_MAP_LAYER_ID, useReal);
      setVisibility("background", true);
      BASE_MAP_LAYER_IDS.forEach((layerId) => {
        if (layerId === "background") {
          return;
        }
        setVisibility(layerId, !useReal);
      });
    },

    updateMapTheme(theme) {
      this.setBaseMapVisibility(theme);
      this.updateSkyTheme(theme);
      this.updateHillshadeTheme(theme);
      this.updateHillshadeVisibility();
      if (theme === "real") {
        this.updateFogTheme(theme);
        return;
      }
      const palette = BASE_MAP_PALETTES[theme] || BASE_MAP_PALETTES.light;
      this.applyMapPalette(palette);
      const labelColor =
        typeof palette.label === "string"
          ? palette.label
          : theme === "dark"
            ? "#e6edf6"
            : "#2f2f2f";
      const haloColor =
        typeof palette.labelHalo === "string"
          ? palette.labelHalo
          : theme === "dark"
            ? "#0f1820"
            : "#ffffff";
      const setPaint = (layer, prop, value) => {
        if (!this.map || !this.map.getLayer(layer)) {
          return;
        }
        try {
          this.map.setPaintProperty(layer, prop, value);
        } catch (error) {
          return;
        }
      };
      [
        "place-label-city",
        "place-label-suburb",
        "place-label-neighbourhood",
        "water-name",
        "transportation-name",
      ].forEach((layerId) => {
        setPaint(layerId, "text-color", labelColor);
        setPaint(layerId, "text-halo-color", haloColor);
      });
      this.updateFogTheme(theme);
    },

    updateSkyTheme(theme) {
      if (!this.map || typeof this.map.setSky !== "function") {
        return;
      }
      if (theme === "real") {
        try {
          this.map.setSky(null);
        } catch (_err) {
          return;
        }
        return;
      }
      const sky = SKY_THEMES[theme] || SKY_THEMES.light;
      try {
        this.map.setSky({ ...sky });
      } catch (_err) {
        return;
      }
    },

    updateHillshadeTheme(theme) {
      if (!this.map || !this.map.getLayer || !this.map.getLayer("dem-hillshade")) {
        return;
      }
      const hillshade = HILLSHADE_THEMES[theme] || HILLSHADE_THEMES.light;
      const setPaint = (prop) => {
        if (!Object.prototype.hasOwnProperty.call(hillshade, prop)) {
          return;
        }
        try {
          this.map.setPaintProperty("dem-hillshade", prop, hillshade[prop]);
        } catch (_err) {
          return;
        }
      };
      [
        "hillshade-exaggeration",
        "hillshade-shadow-color",
        "hillshade-highlight-color",
        "hillshade-accent-color",
        "hillshade-illumination-direction",
        "hillshade-illumination-anchor",
      ].forEach(setPaint);
    },

    updateHillshadeVisibility() {
      if (!this.map || !this.map.getLayer || !this.map.getLayer("dem-hillshade")) {
        return;
      }
      const allow = this.currentTheme !== "real";
      const shouldShow = allow && Boolean(this.terrainEnabled);
      try {
        this.map.setLayoutProperty(
          "dem-hillshade",
          "visibility",
          shouldShow ? "visible" : "none",
        );
      } catch (_err) {
        return;
      }
    },

    updateFogTheme(theme) {
      if (!this.map || typeof this.map.setFog !== "function") {
        return;
      }
      if (theme === "real") {
        try {
          this.map.setFog(null);
        } catch (_err) {
          return;
        }
        return;
      }
      const fog = FOG_THEMES[theme] || FOG_THEMES.light;
      try {
        this.map.setFog({ ...fog });
      } catch (_err) {
        return;
      }
    },

    updateEditModeMapStyle(isEditing) {
      if (!this.map) {
        return;
      }
      if (isEditing) {
        const palette =
          EDIT_MAP_PALETTES[this.currentTheme] || EDIT_MAP_PALETTES.light;
        this.applyMapPalette(palette);
        this.setBaseMapVisibility(this.currentTheme);
        return;
      }
      this.updateMapTheme(this.currentTheme);
    },

      updateCorridorTheme(theme) {
        if (!this.map) {
          return;
        }
        const color = this.getCorridorColor(theme);
      if (this.corridorLayer && this.corridorLayer.setColor) {
        this.corridorLayer.setColor(color);
        this.map.triggerRepaint();
      }
      if (this.corridorLinks3dLayer && this.corridorLinks3dLayer.setColor) {
        this.corridorLinks3dLayer.setColor(color);
        this.map.triggerRepaint();
      }
      if (this.corridorSpareOpen3dLayer && this.corridorSpareOpen3dLayer.setColor) {
        this.corridorSpareOpen3dLayer.setColor(color);
        this.map.triggerRepaint();
      }
        if (this.corridorClosed3dLayer && this.corridorClosed3dLayer.setColor) {
          this.corridorClosed3dLayer.setColor(CORRIDOR_CLOSED_COLOR);
          this.map.triggerRepaint();
        }
        const palette = BASE_MAP_PALETTES[theme] || BASE_MAP_PALETTES.light;
        const labelColor =
          typeof palette.label === "string"
            ? palette.label
            : theme === "dark"
              ? "#eef2f7"
              : "#1f2937";
        const haloColor =
          typeof palette.labelHalo === "string"
            ? palette.labelHalo
            : theme === "dark"
              ? "rgba(12, 18, 26, 0.85)"
              : "rgba(255, 255, 255, 0.9)";
        if (this.map.getLayer && this.map.getLayer("corridor-timer-labels")) {
          try {
            this.map.setPaintProperty("corridor-timer-labels", "text-color", labelColor);
            this.map.setPaintProperty("corridor-timer-labels", "text-halo-color", haloColor);
          } catch (_err) {
            // ignore
          }
        }
        if (this.map.getLayer && this.map.getLayer("corridor-timer-badges")) {
          try {
            this.map.setPaintProperty("corridor-timer-badges", "text-color", labelColor);
            this.map.setPaintProperty("corridor-timer-badges", "text-halo-color", haloColor);
          } catch (_err) {
            // ignore
          }
        }
      },

    clearRouteOverlays() {
      if (!this.map) {
        return;
      }
      this.clearCorridorHover();
      this.clearVertiportHover();
      this.clearCorridorLinkPreview();
      this.clearVertiportZone();
      this.clearVertiportLabels();
      this.clearCorridorScheduleMarkers();
      const map = this.map;
      const removeLayer = (id) => {
        if (map.getLayer(id)) {
          map.removeLayer(id);
        }
      };
      const removeSource = (id) => {
        if (map.getSource(id)) {
          map.removeSource(id);
        }
      };

        [
          "corridor-spare-links-3d",
          "corridor-spare-open-3d",
          "corridor-links-3d",
          "corridor-3d",
          "corridor-closed-3d",
          "corridor-timer-markers",
          "corridor-timer-badges",
          "corridor-timer-labels",
          "corridor-link-preview",
        ].forEach(removeLayer);
        removeSource("corridor-link-preview");
        removeSource("corridor-timer-labels");

      [
        "vertiport-zone-fill",
        "vertiport-zone-outline",
        "vertiport-links-3d",
        "vertiport-circle",
        "vertiport-icon",
        "vertiport-hover-ring",
        "vertiport-edit-ring",
        "vertiport-edit-circle",
      ].forEach(removeLayer);
      removeSource("vertiport-points");
      removeSource("vertiport-links");
      removeSource("vertiport-zone");

        this.corridorLayer = null;
        this.corridorLinks3dLayer = null;
        this.corridorSpareLinks3dLayer = null;
        this.corridorSpareOpen3dLayer = null;
        this.corridorClosed3dLayer = null;
        this.corridorHitData = null;
        this.corridorSpareHitData = null;
        this.corridorData = null;
        this.corridorPointLookup = new Map();
        this.corridorLinkLookup = new Map();
        this.corridorSpareLinkLookup = new Map();
        this.corridorLineByKey = new Map();
        this.corridorSpareLineByKey = new Map();
        this.corridorTimedLabelsNonEmpty = false;
      this.corridorLinkResizeBound = false;
      this.corridorSpareLinkResizeBound = false;
      this.corridorSpareOpenLinkResizeBound = false;
      this.corridorClosedResizeBound = false;
      this.corridorSpareOpenLinkUpdateScheduled = false;
      this.corridorClosedUpdateScheduled = false;
      this.corridorClosedLineIndices = [];
      this.openSpareCorridorEdges = new Set();

      this.vertiportLinks3dLayer = null;
      this.vertiportLinkHitData = null;
      this.vertiportData = null;
      this.vertiportPointLookup = new Map();
      this.vertiportLinkLookup = new Map();
      this.vertiportLinkResizeBound = false;
      this.vertiportLinkUpdateScheduled = false;
      this.planLayersReady = false;
      this.corridorEnsured = false;
      this.vertiportEnsured = false;
    },

    async loadVertiportOverlay(urlOverride, force = false) {
      if (!this.map) {
        return;
      }
      const loadToken = (this.vertiportLoadToken || 0) + 1;
      this.vertiportLoadToken = loadToken;
      const url = urlOverride || this.config.data.vertiportCsv;
      try {
        console.info(`[Vertiport] loading ${url}`);
        const rows = await this.fetchCsvRows(url);
        if (loadToken !== this.vertiportLoadToken) {
          return;
        }
        if (!force && this.config.data.vertiportCsv !== url) {
          return;
        }
        console.info(`[Vertiport] loaded ${rows.length} rows.`);
        this.updateVertiportOverlayFromRows(rows);
      } catch (error) {
        if (loadToken !== this.vertiportLoadToken) {
          return;
        }
        console.warn("Failed to load vertiport overlay.", error);
        if (
          this.map &&
          this.map.isStyleLoaded &&
          this.map.isStyleLoaded() &&
          this.lastVertiportRows &&
          !this.map.getLayer("vertiport-circle")
        ) {
          try {
            this.updateVertiportOverlayFromRows(this.lastVertiportRows);
          } catch (_restoreError) {
            // ignore
          }
        }
      }
    },

    async loadBaseStationOverlay(urlOverride, force = false) {
      if (!this.map) {
        return;
      }
      const url = urlOverride || this.config.data.basestationCsv;
      if (!url) {
        return;
      }
      try {
        const rows = await this.fetchCsvRows(url);
        if (!force && this.config.data.basestationCsv !== url) {
          return;
        }
        this.updateBaseStationOverlayFromRows(rows);
      } catch (error) {
        console.warn("Failed to load base station overlay.", error);
        if (
          this.map &&
          this.map.isStyleLoaded &&
          this.map.isStyleLoaded() &&
          this.lastBaseStationRows &&
          !this.map.getLayer("basestation-icon")
        ) {
          try {
            this.updateBaseStationOverlayFromRows(this.lastBaseStationRows);
          } catch (_restoreError) {
            // ignore
          }
        }
      }
    },

    async loadResourcesVp() {
      if (this.resourcesVpLoaded) {
        return;
      }
      this.resourcesVpLoaded = true;
      try {
        const url = this.resolveApiUrl("api/data/customed/resources_vp.csv");
        const response = await fetch(url, { cache: "no-store" });
        if (response.status === 404) {
          return;
        }
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        const text = await response.text();
        const rows = normalizeRows(parseCsvRows(text));
        if (!rows.length) {
          return;
        }
        const header = rows[0].map((cell) => cell.trim().toLowerCase());
        const idxVertiport = header.indexOf("vertiport");
        const idxLabel = header.indexOf("label");
        const idxZ = header.indexOf("z_m");
        const idxXm = header.indexOf("x_m");
        const idxYm = header.indexOf("y_m");
        const idxXcm = header.indexOf("x_cm");
        const idxYcm = header.indexOf("y_cm");
        const idxZcm = header.indexOf("z_cm");
        const idxLat = header.indexOf("pt_lat_deg");
        const idxLon = header.indexOf("pt_lon_deg");
        if (idxVertiport < 0 || idxLabel < 0 || idxZ < 0) {
          return;
        }
        const altLookup = new Map();
        const resourceLookup = new Map();
        const readNumber = (row, index) => {
          if (index < 0) {
            return NaN;
          }
          const value = Number.parseFloat(readCell(row, index));
          return Number.isFinite(value) ? value : NaN;
        };
        rows.slice(1).forEach((row) => {
          const vp = readCell(row, idxVertiport);
          const label = readCell(row, idxLabel).toUpperCase();
          if (!vp || label !== "FATO 2") {
            return;
          }
          const z = readNumber(row, idxZ);
          if (Number.isFinite(z)) {
            altLookup.set(vp, z);
          }
          const lat = readNumber(row, idxLat);
          const lon = readNumber(row, idxLon);
          const ueX = readNumber(row, idxXm);
          const ueY = readNumber(row, idxYm);
          const ueZ = readNumber(row, idxZ);
          const ueXcm = readNumber(row, idxXcm);
          const ueYcm = readNumber(row, idxYcm);
          const ueZcm = readNumber(row, idxZcm);
          const resolvedUx = Number.isFinite(ueX)
            ? ueX
            : Number.isFinite(ueXcm)
              ? ueXcm / 100.0
              : null;
          const resolvedUy = Number.isFinite(ueY)
            ? ueY
            : Number.isFinite(ueYcm)
              ? ueYcm / 100.0
              : null;
          const resolvedUz = Number.isFinite(ueZ)
            ? ueZ
            : Number.isFinite(ueZcm)
              ? ueZcm / 100.0
              : null;
          if (Number.isFinite(lat) && Number.isFinite(lon)) {
            resourceLookup.set(vp, {
              lat,
              lon,
              alt_m: Number.isFinite(z) ? z : null,
              ue_x: resolvedUx,
              ue_y: resolvedUy,
              ue_z: resolvedUz,
            });
          }
        });
        if (altLookup.size) {
          this.vertiportAltLookup = altLookup;
          if (this.lastVertiportRows) {
            this.updateVertiportOverlayFromRows(this.lastVertiportRows);
          }
        }
        if (resourceLookup.size) {
          this.vertiportResourceLookup = resourceLookup;
        }
      } catch (error) {
        console.warn("Failed to load resources_vp.csv.", error);
      }
    },

    ensureVertiportIcon() {
      if (!this.map) {
        return Promise.resolve(false);
      }
      if (this.vertiportIconPromise) {
        return this.vertiportIconPromise;
      }
      if (this.map.hasImage(VERTIPORT_ICON_ID)) {
        this.vertiportIconPromise = Promise.resolve(true);
        return this.vertiportIconPromise;
      }
      this.vertiportIconPromise = new Promise((resolve) => {
        this.map.loadImage(this.resolveAssetUrl("resources/v_sign.png"), (error, image) => {
          if (error || !image) {
            console.warn("[Vertiport] icon load failed.", error);
            this.vertiportIconPromise = null;
            resolve(false);
            return;
          }
          if (!this.map.hasImage(VERTIPORT_ICON_ID)) {
            this.map.addImage(VERTIPORT_ICON_ID, image);
          }
          this.addVertiportIconLayer();
          resolve(true);
        });
      });
      return this.vertiportIconPromise;
    },

    ensureBaseStationIcon() {
      if (!this.map) {
        return Promise.resolve(false);
      }
      if (this.baseStationIconPromise) {
        return this.baseStationIconPromise;
      }
      if (this.map.hasImage(BASESTATION_ICON_ID)) {
        this.baseStationIconPromise = Promise.resolve(true);
        return this.baseStationIconPromise;
      }
      this.baseStationIconPromise = new Promise((resolve) => {
        this.map.loadImage(
          this.resolveAssetUrl("resources/Basestation.png"),
          (error, image) => {
            if (error || !image) {
              console.warn("[BaseStation] icon load failed.", error);
              this.baseStationIconPromise = null;
              resolve(false);
              return;
            }
            if (!this.map.hasImage(BASESTATION_ICON_ID)) {
              this.map.addImage(BASESTATION_ICON_ID, image);
            }
            this.addBaseStationIconLayer();
            resolve(true);
          }
        );
      });
      return this.baseStationIconPromise;
    },


    updateVertiportOverlayFromRows(rows) {
      this.lastVertiportRows = rows;
      if (!this.map || !this.map.isStyleLoaded()) {
        this.pendingVertiportRows = rows;
        this.vertiportEnsured = false;
        return;
      }
      this.clearVertiportHover();
      this.setVertiportHoverFilter(null);
      this.pendingVertiportRows = null;
      const data = this.buildVertiportFeatures(rows);
      this.vertiportData = data;
      this.vertiportLinkHitData = this.buildVertiportLinkHitData(data);
      this.vertiportPointLookup = new Map(data.points.map((entry) => [entry.name, entry]));
      this.vertiportLinkLookup = new Map(
        data.points.map((entry) => [entry.name, entry.links || []]),
      );
      this.refreshRouteGraph();
      const applyLayers = () => {
        this.setVertiportLayers(data);
        this.setVertiportLabels(data.points);
        this.updateVertiportLinks3dLayer(data);
        this.setupVertiportLinkResize();
        this.map.triggerRepaint();
        this.reorderPlanLayers();
      };
      applyLayers();
      this.bindVertiportStyleReload();
    },

    bindVertiportStyleReload() {
      if (!this.map || this.vertiportStyleReloadBound) {
        return;
      }
      this.vertiportStyleReloadBound = true;
      this.map.on("styledata", () => {
        if (!this.map || !this.map.isStyleLoaded || !this.map.isStyleLoaded()) {
          return;
        }
        this.ensureVertiportOverlayVisible();
      });
    },

    ensureVertiportOverlayVisible() {
      if (
        !this.map ||
        !this.vertiportData ||
        !this.map.isStyleLoaded ||
        !this.map.isStyleLoaded()
      ) {
        return;
      }
      const map = this.map;
      const needsPoints = !map.getSource || !map.getSource("vertiport-points");
      const needsLayers = !map.getLayer || !map.getLayer("vertiport-circle");
      if (needsPoints || needsLayers) {
        try {
          this.setVertiportLayers(this.vertiportData);
        } catch (error) {
          console.warn("[Vertiport] overlay restore failed.", error);
          return;
        }
      }
      if (!this.vertiportLabels || !this.vertiportLabels.length) {
        this.setVertiportLabels(this.vertiportData.points);
      }
      const has3dLayer = map.getLayer && map.getLayer("vertiport-links-3d");
      if (!this.vertiportLinks3dLayer) {
        this.ensurePlanLayers();
      } else if (!has3dLayer) {
        try {
          map.addLayer(this.vertiportLinks3dLayer);
        } catch (error) {
          console.warn("[Vertiport] 3d link layer restore failed.", error);
          this.vertiportLinks3dLayer = null;
          this.planLayersReady = false;
          this.ensurePlanLayers();
        }
      }
      this.updateVertiportLinks3dLayer(this.vertiportData);
      this.reorderPlanLayers();
      this.map.triggerRepaint();
    },

    updateBaseStationOverlayFromRows(rows) {
      this.lastBaseStationRows = rows;
      if (!this.map || !this.map.isStyleLoaded()) {
        this.pendingBaseStationRows = rows;
        this.baseStationEnsured = false;
        return;
      }
      this.pendingBaseStationRows = null;
      const data = this.buildBaseStationFeatures(rows);
      this.baseStationData = data;
      this.baseStationPointLookup = new Map(data.points.map((entry) => [entry.name, entry]));
      this.syncBaseStationSequence();
      this.setBaseStationLayers(data);
      this.map.triggerRepaint();
      this.reorderPlanLayers();
    },

    buildVertiportFeatures(rows) {
      const points = [];
      const lines = [];
      const lookup = new Map();
      const corridorLookup = this.corridorPointLookup || new Map();
      // getDataRows() strips header rows, so links must be read from schema index.
      const linkIndex = 10;
      const linkStats = {
        total: 0,
        resolved: 0,
        missing: new Set(),
      };
      const parseLinks = (row) => {
        if (!row || !row.length) {
          return [];
        }
        const index = linkIndex;
        if (row.length <= index) {
          return [];
        }
        const parts = [];
        const base = readCell(row, index);
        if (base) {
          parts.push(base);
        }
        if (row.length > index + 1) {
          row.slice(index + 1).forEach((cell) => {
            const value = String(cell || "").trim();
            if (value) {
              parts.push(value);
            }
          });
        }
        const linkCell = parts.join(", ");
        if (!linkCell) {
          return [];
        }
        return linkCell
          .split(",")
          .map((value) => value.trim())
          .filter((value) => value.length > 0);
      };

      rows.forEach((row) => {
        const name = readCell(row, 0);
        const lat = Number.parseFloat(readCell(row, 2));
        const lon = Number.parseFloat(readCell(row, 3));
        if (!name || !Number.isFinite(lat) || !Number.isFinite(lon)) {
          return;
        }
        const mtrKm = Number.parseFloat(readCell(row, 6));
        const entry = {
          id: name,
          name,
          coord: [lon, lat],
          className: readCell(row, 1),
          altitude_m: VERTIPORT_ALT_M,
          mtr_km: Number.isFinite(mtrKm) ? mtrKm : null,
          links: parseLinks(row),
        };
        lookup.set(name, entry);
        points.push(entry);
      });

      const seen = new Set();
      let lineIndex = 0;
      rows.forEach((row) => {
        const name = readCell(row, 0);
        const startEntry = lookup.get(name);
        if (!startEntry) {
          return;
        }
        if (!startEntry.links || startEntry.links.length === 0) {
          return;
        }
        startEntry.links.forEach((target) => {
          if (!target) {
            return;
          }
          linkStats.total += 1;
          const endEntry = corridorLookup.get(target) || lookup.get(target);
          if (!endEntry) {
            linkStats.missing.add(target);
            return;
          }
          linkStats.resolved += 1;
          const key = [name, target].sort().join("|");
          if (seen.has(key)) {
            return;
          }
          seen.add(key);
          lines.push({
            id: lineIndex,
            from: name,
            to: target,
            start: startEntry,
            end: endEntry,
          });
          lineIndex += 1;
        });
      });

      if (linkStats.total) {
        const missing = Array.from(linkStats.missing);
        console.info(
          `[Vertiport Links] corridor nodes: ${corridorLookup.size}, resolved ${linkStats.resolved}/${linkStats.total}, unique lines: ${lines.length}.`,
        );
        if (missing.length) {
          console.warn("[Vertiport Links] missing targets:", missing);
        }
      } else {
        console.warn("[Vertiport Links] no link entries found.");
      }
      return { points, lines };
    },

    buildVertiportPointGeoJson(points) {
      return {
        type: "FeatureCollection",
        features: points.map((entry) => ({
          type: "Feature",
          id: entry.id,
          geometry: {
            type: "Point",
            coordinates: entry.coord,
          },
          properties: {
            name: entry.name,
            class: entry.className || "",
          },
        })),
      };
    },

    buildVertiportLineGeoJson(lines) {
      return {
        type: "FeatureCollection",
        features: lines.map((line) => ({
          type: "Feature",
          id: line.id,
          geometry: {
            type: "LineString",
            coordinates: [line.start.coord, line.end.coord],
          },
          properties: {
            from: line.from,
            to: line.to,
            name: `${line.from} - ${line.to}`,
          },
        })),
      };
    },

    buildBaseStationFeatures(rows) {
      const points = [];
      const seen = new Set();
      rows.forEach((row) => {
        const name = readCell(row, 0);
        const lat = Number.parseFloat(readCell(row, 1));
        const lon = Number.parseFloat(readCell(row, 2));
        if (!name || !Number.isFinite(lat) || !Number.isFinite(lon)) {
          return;
        }
        if (seen.has(name)) {
          return;
        }
        seen.add(name);
        points.push({
          id: name,
          name,
          coord: [lon, lat],
        });
      });
      return { points };
    },

    buildBaseStationPointGeoJson(points) {
      return {
        type: "FeatureCollection",
        features: points.map((entry) => ({
          type: "Feature",
          id: entry.id,
          geometry: {
            type: "Point",
            coordinates: entry.coord,
          },
          properties: {
            name: entry.name,
          },
        })),
      };
    },

    setBaseStationLayers(data) {
      const map = this.map;
      if (!map) {
        return;
      }
      const pointSourceId = "basestation-points";
      const pointData = this.buildBaseStationPointGeoJson(data.points);

      if (map.getSource(pointSourceId)) {
        map.getSource(pointSourceId).setData(pointData);
      } else {
        map.addSource(pointSourceId, { type: "geojson", data: pointData });
      }

      const beforeId = map.getLayer("vertiport-circle") ? "vertiport-circle" : null;
      if (map.hasImage(BASESTATION_ICON_ID)) {
        this.addBaseStationIconLayer(beforeId);
      } else if (this.ensureBaseStationIcon) {
        this.ensureBaseStationIcon().then((ok) => {
          if (ok) {
            this.addBaseStationIconLayer(beforeId);
          }
        });
      }
      this.addBaseStationEditRing(beforeId);
    },

    addBaseStationIconLayer(beforeId) {
      const map = this.map;
      if (!map || !map.getSource("basestation-points")) {
        return;
      }
      if (map.getLayer("basestation-icon")) {
        return;
      }
      const insertBefore = beforeId && map.getLayer(beforeId) ? beforeId : null;
      const addLayer = (layer) => {
        if (insertBefore) {
          map.addLayer(layer, insertBefore);
        } else {
          map.addLayer(layer);
        }
      };
      addLayer(
        {
          id: "basestation-icon",
          type: "symbol",
          source: "basestation-points",
          layout: {
            "icon-image": BASESTATION_ICON_ID,
            "icon-size": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              0.011 * MAP_SIZE_SCALE,
              10,
              0.015 * MAP_SIZE_SCALE,
              13,
              0.018 * MAP_SIZE_SCALE,
            ],
            "icon-allow-overlap": true,
            "icon-anchor": "center",
            "icon-rotation-alignment": "viewport",
            "icon-pitch-alignment": "viewport",
          },
        },
      );
    },

    addBaseStationEditRing(beforeId) {
      const map = this.map;
      if (!map || !map.getSource("basestation-points")) {
        return;
      }
      if (map.getLayer("basestation-edit-ring")) {
        return;
      }
      const insertBefore = beforeId && map.getLayer(beforeId) ? beforeId : null;
      const addLayer = (layer) => {
        if (insertBefore) {
          map.addLayer(layer, insertBefore);
        } else {
          map.addLayer(layer);
        }
      };
      addLayer(
        {
          id: "basestation-edit-ring",
          type: "circle",
          source: "basestation-points",
          filter: ["==", ["get", "name"], ""],
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              7 * MAP_SIZE_SCALE,
              12,
              14 * MAP_SIZE_SCALE,
            ],
            "circle-color": "#000000",
            "circle-opacity": 0,
            "circle-stroke-color": "#6f8cff",
            "circle-stroke-opacity": 0.95,
            "circle-stroke-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              2 * MAP_SIZE_SCALE,
              12,
              4 * MAP_SIZE_SCALE,
            ],
          },
        },
      );
    },

    setBaseStationEditHighlight(name) {
      if (!this.map || !this.map.getLayer("basestation-edit-ring")) {
        return;
      }
      const next = name ? String(name) : "";
      if (this.baseStationEditHighlightName === next) {
        return;
      }
      this.baseStationEditHighlightName = next;
      this.map.setFilter("basestation-edit-ring", ["==", ["get", "name"], next]);
    },

    clearBaseStationEditHighlight() {
      if (!this.map || !this.map.getLayer("basestation-edit-ring")) {
        this.baseStationEditHighlightName = "";
        return;
      }
      if (!this.baseStationEditHighlightName) {
        return;
      }
      this.baseStationEditHighlightName = "";
      this.map.setFilter("basestation-edit-ring", ["==", ["get", "name"], ""]);
    },

    ensureBaseStationEditLayer() {
      if (!this.map) {
        return;
      }
      const sourceId = "basestation-edit";
      if (!this.map.getSource(sourceId)) {
        this.map.addSource(sourceId, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!this.map.getLayer("basestation-edit-circle")) {
        this.map.addLayer({
          id: "basestation-edit-circle",
          type: "circle",
          source: sourceId,
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              5 * MAP_SIZE_SCALE,
              12,
              9 * MAP_SIZE_SCALE,
            ],
            "circle-color": "#ffffff",
            "circle-stroke-color": "#6f8cff",
            "circle-stroke-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              1.6 * MAP_SIZE_SCALE,
              12,
              3 * MAP_SIZE_SCALE,
            ],
          },
        });
      }
      this.updateBaseStationEditSource();
    },

    updateBaseStationEditSource() {
      if (!this.map) {
        return;
      }
      const source = this.map.getSource("basestation-edit");
      if (!source) {
        return;
      }
      const features = [];
      this.baseStationPendingNodes.forEach((node) => {
        if (!node || !node.lngLat) {
          return;
        }
        features.push({
          type: "Feature",
          id: node.id,
          geometry: {
            type: "Point",
            coordinates: [node.lngLat.lng, node.lngLat.lat],
          },
          properties: { kind: "pending", nodeId: node.id },
        });
      });
      source.setData({ type: "FeatureCollection", features });
    },

    pickPendingBaseStationAt(point) {
      if (!this.map) {
        return null;
      }
      if (!this.map.getLayer("basestation-edit-circle")) {
        return null;
      }
      const features = this.map.queryRenderedFeatures(point, {
        layers: ["basestation-edit-circle"],
      });
      if (!features.length) {
        return null;
      }
      const target = features.find(
        (feature) => feature.properties && feature.properties.kind === "pending",
      );
      if (!target) {
        return null;
      }
      const props = target.properties || {};
      const id = props.nodeId || target.id;
      return id ? String(id) : null;
    },

    createPendingBaseStationNode(lngLat) {
      if (!this.map || !lngLat) {
        return null;
      }
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return null;
      }
      const id = `pending-${(this.baseStationPendingCounter += 1)}`;
      const node = { id, lngLat: normalized };
      this.baseStationPendingNodes.set(id, node);
      this.ensureBaseStationEditLayer();
      this.updateBaseStationEditSource();
      return node;
    },

    updatePendingBaseStationNodePosition(node, lngLat) {
      if (!node || !lngLat) {
        return;
      }
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return;
      }
      node.lngLat = normalized;
      this.updateBaseStationEditSource();
    },

    removePendingBaseStationNode(nodeId) {
      const node = this.baseStationPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      this.baseStationPendingNodes.delete(nodeId);
      this.updateBaseStationEditSource();
      if (this.baseStationEditPopupNodeId === nodeId) {
        this.hideBaseStationEditPopup();
      }
      if (this.baseStationEditMovingId === nodeId) {
        this.baseStationEditMovingId = null;
      }
    },

    ensureBaseStationEditPopup() {
      if (this.baseStationEditPopup) {
        return this.baseStationEditPopup;
      }
      const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: true,
        className: "vertiport-edit-popup",
      });
      if (popup.on) {
        popup.on("close", () => {
          this.baseStationEditPopupNodeId = null;
          this.baseStationEditPopupName = null;
          if (!this.baseStationEditMovingName) {
            this.clearBaseStationEditHighlight();
          }
        });
      }
      this.baseStationEditPopup = popup;
      return popup;
    },

    hideBaseStationEditPopup() {
      if (this.baseStationEditPopup) {
        this.baseStationEditPopup.remove();
      }
      this.baseStationEditPopupNodeId = null;
      this.baseStationEditPopupName = null;
    },

    toggleBaseStationPendingPopup(nodeId) {
      if (!this.map) {
        return;
      }
      const node = this.baseStationPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      if (this.baseStationEditPopupNodeId === nodeId) {
        this.hideBaseStationEditPopup();
        return;
      }
      const popup = this.ensureBaseStationEditPopup();
      popup
        .setLngLat(node.lngLat)
        .setDOMContent(this.buildBaseStationPendingPopupContent(nodeId))
        .addTo(this.map);
      this.baseStationEditPopupNodeId = nodeId;
      this.baseStationEditPopupName = null;
    },

    buildBaseStationPendingPopupContent(nodeId) {
      const card = document.createElement("div");
      card.className = "vertiport-edit-card";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Base Station";
      card.appendChild(title);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions vertiport-edit-actions-wide";

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Move", () => {
          this.baseStationEditMovingId = nodeId;
          this.hideBaseStationEditPopup();
        }),
      );
      actions.appendChild(
        buildButton("Delete", () => {
          this.removePendingBaseStationNode(nodeId);
        }),
      );
      actions.appendChild(
        buildButton("Confirm", () => {
          this.showBaseStationConfirmPopup(nodeId);
        }),
      );
      card.appendChild(actions);
      return card;
    },

    showBaseStationConfirmPopup(nodeId) {
      if (!this.map) {
        return;
      }
      const node = this.baseStationPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      const popup = this.ensureBaseStationEditPopup();
      const card = document.createElement("div");
      card.className = "vertiport-edit-card vertiport-edit-confirm";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Enter name";
      card.appendChild(title);
      const body = document.createElement("div");
      body.className = "vertiport-edit-confirm-body";
      card.appendChild(body);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions";
      card.appendChild(actions);

      const input = document.createElement("input");
      input.type = "text";
      input.className = "vertiport-edit-input";
      input.placeholder = "Name";
      body.appendChild(input);

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Cancel", () => {
          this.hideBaseStationEditPopup();
        }),
      );
      actions.appendChild(
        buildButton("Save", () => {
          const value = input.value.trim();
          if (!value) {
            this.addStatusMessage({
              text: "Enter a name first.",
              level: "warn",
              ttlMs: 2500,
            });
            return;
          }
          void this.commitPendingBaseStation(nodeId, value);
        }),
      );

      popup
        .setLngLat(node.lngLat)
        .setDOMContent(card)
        .addTo(this.map);
      this.baseStationEditPopupNodeId = nodeId;
      this.baseStationEditPopupName = null;
      input.focus();
    },

    toggleBaseStationExistingPopup(name, lngLat) {
      if (!this.map) {
        return;
      }
      const entry = this.baseStationPointLookup ? this.baseStationPointLookup.get(name) : null;
      if (!entry) {
        return;
      }
      if (this.baseStationEditPopupName === name) {
        this.hideBaseStationEditPopup();
        this.clearBaseStationEditHighlight();
        return;
      }
      const anchorLngLat =
        lngLat && Number.isFinite(lngLat.lng) && Number.isFinite(lngLat.lat)
          ? lngLat
          : { lng: entry.coord[0], lat: entry.coord[1] };
      const popup = this.ensureBaseStationEditPopup();
      popup
        .setLngLat(anchorLngLat)
        .setDOMContent(this.buildBaseStationExistingPopupContent(name))
        .addTo(this.map);
      this.baseStationEditPopupNodeId = null;
      this.baseStationEditPopupName = name;
    },

    buildBaseStationExistingPopupContent(name) {
      const entry = this.baseStationPointLookup ? this.baseStationPointLookup.get(name) : null;
      const card = document.createElement("div");
      card.className = "vertiport-edit-card";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      const titleText =
        entry && entry.name
          ? this.t("label.base_station_named", { name: entry.name })
          : this.translateLiteral("Base Station");
      title.textContent = titleText;
      card.appendChild(title);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions vertiport-edit-actions-wide";

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Move", () => {
          if (!entry || !entry.coord) {
            return;
          }
          this.baseStationEditMovingName = name;
          this.setBaseStationEditHighlight(name);
          this.hideBaseStationEditPopup();
          this.addStatusMessage({
            text: "Click map to set new base station position.",
            level: "info",
            ttlMs: 3500,
          });
        }),
      );
      actions.appendChild(
        buildButton("Delete", () => {
          void this.deleteExistingBaseStation(name);
        }),
      );
      card.appendChild(actions);
      return card;
    },

    syncBaseStationSequence() {
      const lookup = this.baseStationPointLookup;
      if (!lookup || lookup.size === 0) {
        this.baseStationSequence = 1;
        return;
      }
      let maxValue = 0;
      lookup.forEach((_entry, name) => {
        const match = String(name).match(/^BS[-_]?(\d+)$/i);
        if (!match) {
          return;
        }
        const value = Number.parseInt(match[1], 10);
        if (Number.isFinite(value)) {
          maxValue = Math.max(maxValue, value);
        }
      });
      this.baseStationSequence = Math.max(this.baseStationSequence || 1, maxValue + 1);
    },

    getNextBaseStationName() {
      const lookup = this.baseStationPointLookup || new Map();
      let sequence = Number.isFinite(this.baseStationSequence)
        ? this.baseStationSequence
        : 1;
      const formatName = (value) => `BS-${String(value).padStart(3, "0")}`;
      let name = formatName(sequence);
      while (lookup.has(name)) {
        sequence += 1;
        name = formatName(sequence);
      }
      this.baseStationSequence = sequence + 1;
      return name;
    },

    setVertiportLayers(data) {
      const map = this.map;
      if (!map) {
        return;
      }
      const pointSourceId = "vertiport-points";
      const lineSourceId = "vertiport-links";
      const pointData = this.buildVertiportPointGeoJson(data.points);
      const lineData = this.buildVertiportLineGeoJson(data.lines);

      if (map.getSource(pointSourceId)) {
        map.getSource(pointSourceId).setData(pointData);
      } else {
        map.addSource(pointSourceId, { type: "geojson", data: pointData });
      }

      if (map.getSource(lineSourceId)) {
        map.getSource(lineSourceId).setData(lineData);
      } else {
        map.addSource(lineSourceId, { type: "geojson", data: lineData });
      }

      const beforeId = map.getLayer("corridor-3d") ? "corridor-3d" : null;
      const addLayer = (layer) => {
        if (beforeId && map.getLayer(beforeId)) {
          map.addLayer(layer, beforeId);
        } else {
          map.addLayer(layer);
        }
      };

      if (!map.getLayer("vertiport-circle")) {
        const hoverExpr = ["boolean", ["feature-state", "hover"], false];
        addLayer(
          {
            id: "vertiport-circle",
            type: "circle",
            source: pointSourceId,
            paint: {
              "circle-radius": [
                "interpolate",
                ["linear"],
                ["zoom"],
                6,
                4 * MAP_SIZE_SCALE,
                12,
                8 * MAP_SIZE_SCALE,
              ],
              "circle-color": [
                "case",
                hoverExpr,
                "#f2fff8",
                "#ffffff",
              ],
              "circle-stroke-color": [
                "case",
                hoverExpr,
                "#8dffbb",
                "#1a1a1a",
              ],
              "circle-stroke-width": [
                "interpolate",
                ["linear"],
                ["zoom"],
                6,
                0.8 * MAP_SIZE_SCALE,
                12,
                1.2 * MAP_SIZE_SCALE,
              ],
            },
          },
        );
      }

      if (map.hasImage(VERTIPORT_ICON_ID)) {
        this.addVertiportIconLayer(beforeId);
      } else if (this.ensureVertiportIcon) {
        this.ensureVertiportIcon().then((ok) => {
          if (ok) {
            this.addVertiportIconLayer(beforeId);
          }
        });
      }
      this.addVertiportHoverRing(beforeId);
      this.addVertiportEditRing(beforeId);
    },

    addVertiportHoverRing(beforeId) {
      const map = this.map;
      if (!map || !map.getSource("vertiport-points")) {
        return;
      }
      if (map.getLayer("vertiport-hover-ring")) {
        return;
      }
      const insertBefore = beforeId && map.getLayer(beforeId) ? beforeId : null;
      const addLayer = (layer) => {
        if (insertBefore) {
          map.addLayer(layer, insertBefore);
        } else {
          map.addLayer(layer);
        }
      };
      addLayer(
        {
          id: "vertiport-hover-ring",
          type: "circle",
          source: "vertiport-points",
          filter: ["==", ["get", "name"], ""],
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              6 * MAP_SIZE_SCALE,
              12,
              12 * MAP_SIZE_SCALE,
            ],
            "circle-color": "#000000",
            "circle-opacity": 0,
            "circle-stroke-color": "#8dffbb",
            "circle-stroke-opacity": 0.95,
            "circle-stroke-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              2 * MAP_SIZE_SCALE,
              12,
              3.5 * MAP_SIZE_SCALE,
            ],
          },
        },
      );
    },

    addVertiportEditRing(beforeId) {
      const map = this.map;
      if (!map || !map.getSource("vertiport-points")) {
        return;
      }
      if (map.getLayer("vertiport-edit-ring")) {
        return;
      }
      const insertBefore = beforeId && map.getLayer(beforeId) ? beforeId : null;
      const addLayer = (layer) => {
        if (insertBefore) {
          map.addLayer(layer, insertBefore);
        } else {
          map.addLayer(layer);
        }
      };
      addLayer(
        {
          id: "vertiport-edit-ring",
          type: "circle",
          source: "vertiport-points",
          filter: ["==", ["get", "name"], ""],
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              7 * MAP_SIZE_SCALE,
              12,
              14 * MAP_SIZE_SCALE,
            ],
            "circle-color": "#000000",
            "circle-opacity": 0,
            "circle-stroke-color": "#ffb347",
            "circle-stroke-opacity": 0.95,
            "circle-stroke-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              2.2 * MAP_SIZE_SCALE,
              12,
              4 * MAP_SIZE_SCALE,
            ],
          },
        },
      );
    },

    setVertiportHoverFilter(name) {
      if (!this.map || !this.map.getLayer("vertiport-hover-ring")) {
        return;
      }
      if (this.vertiportHoverName === name) {
        return;
      }
      this.vertiportHoverName = name || "";
      this.map.setFilter("vertiport-hover-ring", [
        "==",
        ["get", "name"],
        this.vertiportHoverName,
      ]);
    },

    setVertiportEditHighlight(name) {
      if (!this.map || !this.map.getLayer("vertiport-edit-ring")) {
        return;
      }
      const next = name ? String(name) : "";
      if (this.vertiportEditHighlightName === next) {
        return;
      }
      this.vertiportEditHighlightName = next;
      this.map.setFilter("vertiport-edit-ring", ["==", ["get", "name"], next]);
    },

    clearVertiportEditHighlight() {
      if (!this.map || !this.map.getLayer("vertiport-edit-ring")) {
        this.vertiportEditHighlightName = "";
        return;
      }
      if (!this.vertiportEditHighlightName) {
        return;
      }
      this.vertiportEditHighlightName = "";
      this.map.setFilter("vertiport-edit-ring", ["==", ["get", "name"], ""]);
    },

    clearVertiportLabels() {
      this.vertiportLabels.forEach((marker) => marker.remove());
      this.vertiportLabels = [];
    },

    clearCorridorScheduleMarkers() {
      if (!this.corridorScheduleMarkers) {
        this.corridorScheduleMarkers = new Map();
        return;
      }
      this.corridorScheduleMarkers.forEach((marker) => marker.remove());
      this.corridorScheduleMarkers.clear();
    },

    setVertiportLabels(points) {
      if (!this.map) {
        return;
      }
      if (!this.vertiportLabelZoomBound && this.map.on) {
        this.vertiportLabelZoomBound = true;
        this.map.on("zoom", () => this.updateVertiportLabelScale());
      }
      this.clearVertiportLabels();
      points.forEach((entry) => {
        const label = document.createElement("div");
        label.className = "vertiport-static-label";
        const text = document.createElement("div");
        text.className = "vertiport-static-label-text";
        text.textContent = entry.name;
        label.appendChild(text);
        const marker = new maplibregl.Marker({
          element: label,
          anchor: "top",
          offset: [0, 8 * MAP_SIZE_SCALE],
        })
          .setLngLat(entry.coord)
          .addTo(this.map);
        this.vertiportLabels.push(marker);
      });
      this.updateVertiportLabelScale();
    },

    updateVertiportLabelScale() {
      if (!this.map || !this.vertiportLabels || !this.vertiportLabels.length) {
        return;
      }
      const zoom = this.map.getZoom ? this.map.getZoom() : 12;
      const scale = this.getZoomScale(zoom, {
        minZoom: 6,
        maxZoom: 12,
        minScale: 0.55,
        maxScale: 1,
      });
      this.vertiportLabels.forEach((marker) => {
        const element = marker.getElement ? marker.getElement() : null;
        if (!element || !element.querySelector) {
          return;
        }
        const textNode = element.querySelector(".vertiport-static-label-text");
        if (textNode) {
          textNode.style.transform = `scale(${scale})`;
        }
      });
    },

    addVertiportIconLayer(beforeId) {
      const map = this.map;
      if (!map || !map.getSource("vertiport-points")) {
        return;
      }
      if (map.getLayer("vertiport-icon")) {
        return;
      }
      const insertBefore = beforeId && map.getLayer(beforeId) ? beforeId : null;
      const addLayer = (layer) => {
        if (insertBefore) {
          map.addLayer(layer, insertBefore);
        } else {
          map.addLayer(layer);
        }
      };
      addLayer(
        {
          id: "vertiport-icon",
          type: "symbol",
          source: "vertiport-points",
          layout: {
            "icon-image": VERTIPORT_ICON_ID,
            "icon-size": [
              "interpolate",
              ["linear"],
              ["zoom"],
              6,
              0.011 * MAP_SIZE_SCALE,
              10,
              0.015 * MAP_SIZE_SCALE,
              13,
              0.018 * MAP_SIZE_SCALE,
            ],
            "icon-allow-overlap": true,
            "icon-anchor": "center",
            "icon-rotation-alignment": "viewport",
            "icon-pitch-alignment": "viewport",
          },
        },
      );
    },

    async loadCorridorOverlay(urlOverride, force = false) {
      if (!this.map) {
        return;
      }
      const loadToken = (this.corridorLoadToken || 0) + 1;
      this.corridorLoadToken = loadToken;
      const url = urlOverride || this.config.data.waypointCsv;
      try {
        console.info(`[Corridor] loading ${url}`);
        const rows = await this.fetchCsvRows(url);
        if (loadToken !== this.corridorLoadToken) {
          return;
        }
        if (!force && this.config.data.waypointCsv !== url) {
          return;
        }
        console.info(`[Corridor] loaded ${rows.length} rows.`);
        this.updateCorridorOverlayFromRows(rows);
      } catch (error) {
        if (loadToken !== this.corridorLoadToken) {
          return;
        }
        console.warn("Failed to load corridor overlay.", error);
        if (
          this.map &&
          this.map.isStyleLoaded &&
          this.map.isStyleLoaded() &&
          this.lastCorridorRows &&
          !this.map.getLayer("corridor-3d")
        ) {
          try {
            this.updateCorridorOverlayFromRows(this.lastCorridorRows);
          } catch (_restoreError) {
            // ignore
          }
        }
      }
    },

    ensureCorridorReady() {
      if (!this.map || this.corridorEnsured) {
        return;
      }
      this.corridorEnsured = true;
      if (this.pendingCorridorRows) {
        const rows = this.pendingCorridorRows;
        this.pendingCorridorRows = null;
        this.updateCorridorOverlayFromRows(rows);
        return;
      }
      if (this.lastCorridorRows) {
        this.updateCorridorOverlayFromRows(this.lastCorridorRows);
        return;
      }
      const info = this.defaultFiles.corridor;
      if (info && info.url) {
        this.loadCorridorData(info.url);
      }
    },

    ensureVertiportReady() {
      if (!this.map || this.vertiportEnsured) {
        return;
      }
      this.vertiportEnsured = true;
      if (this.pendingVertiportRows) {
        const rows = this.pendingVertiportRows;
        this.pendingVertiportRows = null;
        this.updateVertiportOverlayFromRows(rows);
        return;
      }
      if (this.lastVertiportRows) {
        this.updateVertiportOverlayFromRows(this.lastVertiportRows);
        return;
      }
      const info = this.defaultFiles.vertiport;
      if (info && info.url) {
        if (this.tableBodies && this.tableBodies.vertiport) {
          this.loadVertiportTable(info.url, true);
        } else {
          this.loadVertiportOverlay(info.url, true);
        }
      }
    },

    ensureBaseStationReady() {
      if (!this.map || this.baseStationEnsured) {
        return;
      }
      this.baseStationEnsured = true;
      if (this.pendingBaseStationRows) {
        const rows = this.pendingBaseStationRows;
        this.pendingBaseStationRows = null;
        this.updateBaseStationOverlayFromRows(rows);
        return;
      }
      if (this.lastBaseStationRows) {
        this.updateBaseStationOverlayFromRows(this.lastBaseStationRows);
        return;
      }
      const info = this.defaultFiles.basestation;
      if (info && info.url) {
        // JY - Base station default spawn: load default base station CSV when no rows are present.
        this.loadBaseStationOverlay(info.url, true);
      }
    },

    updateCorridorOverlayFromRows(rows) {
      this.lastCorridorRows = rows;
      if (!this.map || !this.map.isStyleLoaded()) {
        this.pendingCorridorRows = rows;
        return;
      }
      this.pendingCorridorRows = null;
      const data = this.buildCorridorFeatures(rows);
        console.info(
          `[Corridor] points: ${data.points.length}, links: ${data.lines.length}.`,
        );
        this.corridorData = data;
        this.corridorPointLookup = new Map(data.points.map((entry) => [entry.name, entry]));
        const lineByKey = new Map();
        const spareLineByKey = new Map();
        if (Array.isArray(data.lines)) {
          data.lines.forEach((line) => {
            const key = this.getCorridorEdgeKey(line.from, line.to);
            if (key) {
              lineByKey.set(key, line);
            }
          });
        }
        if (Array.isArray(data.spareLines)) {
          data.spareLines.forEach((line) => {
            const key = this.getCorridorEdgeKey(line.from, line.to);
            if (key) {
              spareLineByKey.set(key, line);
            }
          });
        }
        this.corridorLineByKey = lineByKey;
        this.corridorSpareLineByKey = spareLineByKey;
        const linkLookup = new Map();
        const spareLookup = new Map();
      rows.forEach((row) => {
        const name = readCell(row, 0);
        if (!name) {
          return;
        }
        linkLookup.set(name, this.parseCorridorLinkList(readCell(row, 4)));
        spareLookup.set(name, this.parseCorridorLinkList(readCell(row, 5)));
      });
      this.corridorLinkLookup = linkLookup;
      this.corridorSpareLinkLookup = spareLookup;
      this.corridorHitData = this.buildCorridorHitData(data);
      this.corridorSpareHitData = this.buildCorridorSpareHitData(data);
      this.syncOpenSpareEdges(data);
      this.clearCorridorHover();
      this.hideCorridorPopup();
      this.refreshRouteGraph();
      const hasLayer =
        this.corridorLayer && this.map.getLayer && this.map.getLayer(this.corridorLayer.id);
      if (hasLayer && this.corridorLayer.updateBuffers) {
        const buffers = this.buildCorridorBuffers(data);
        this.corridorLayer.updateBuffers(buffers);
      } else {
        this.setCorridorLayer(data);
      }
      this.ensureCorridorLinkLayer();
      this.updateCorridorLinks3dLayer(data);
      this.setupCorridorLinkResize();
      this.ensureCorridorSpareLinkLayer();
      this.updateCorridorSpareLinks3dLayer(data);
      this.setupCorridorSpareLinkResize();
        this.ensureCorridorSpareOpenLayer();
        this.updateCorridorSpareOpen3dLayer(data);
        this.setupCorridorSpareOpenResize();
        this.ensureCorridorClosedLayer();
        this.setupCorridorClosedResize();
        this.refreshClosedCorridorLines();
        this.ensureCorridorTimerLabelLayer();
        this.updateCorridorTimedLabels(this.lastSimTime_s);
        this.updateCorridorTheme(this.currentTheme);
        this.map.triggerRepaint();
      this.reorderPlanLayers();
      requestAnimationFrame(() => {
        if (this.map) {
          this.map.triggerRepaint();
        }
      });
      if (this.map && this.map.getSource && this.map.getSource("corridor-edit")) {
        this.updateCorridorEditSource();
        this.updateCorridorEditSelection();
      }
      if (this.lastVertiportRows) {
        this.updateVertiportOverlayFromRows(this.lastVertiportRows);
      }
    },

    syncOpenSpareEdges(data) {
      if (!this.openSpareCorridorEdges || !this.openSpareCorridorEdges.size) {
        return;
      }
      const valid = new Set();
      if (data && Array.isArray(data.spareLines)) {
        data.spareLines.forEach((line) => {
          const key = this.getCorridorEdgeKey(line.from, line.to);
          if (key) {
            valid.add(key);
          }
        });
      }
      Array.from(this.openSpareCorridorEdges).forEach((key) => {
        if (!valid.has(key)) {
          this.openSpareCorridorEdges.delete(key);
        }
      });
    },

    buildCorridorFeatures(rows) {
      const points = [];
      const lines = [];
      const spareLines = [];
      const lookup = new Map();
      rows.forEach((row) => {
        const name = readCell(row, 0);
        const lat = Number.parseFloat(readCell(row, 1));
        const lon = Number.parseFloat(readCell(row, 2));
        if (!name || !Number.isFinite(lat) || !Number.isFinite(lon)) {
          return;
        }
        const coord = [lon, lat];
        const entry = { name, coord, altitude_m: CORRIDOR_ALT_M };
        lookup.set(name, entry);
        points.push(entry);
      });

      const seen = new Set();
      const spareSeen = new Set();
      rows.forEach((row) => {
        const name = readCell(row, 0);
        const startEntry = lookup.get(name);
        if (!startEntry) {
          return;
        }
        const linkCell = readCell(row, 4);
        if (linkCell) {
          linkCell.split(",").forEach((raw) => {
            const target = raw.trim();
            if (!target) {
              return;
            }
            const endEntry = lookup.get(target);
            if (!endEntry) {
              return;
            }
            const key = [name, target].sort().join("|");
            if (seen.has(key)) {
              return;
            }
            seen.add(key);
            lines.push({
              from: name,
              to: target,
              start: startEntry,
              end: endEntry,
            });
          });
        }
        const spareCell = readCell(row, 5);
        if (spareCell) {
          spareCell.split(",").forEach((raw) => {
            const target = raw.trim();
            if (!target) {
              return;
            }
            const endEntry = lookup.get(target);
            if (!endEntry) {
              return;
            }
            const key = [name, target].sort().join("|");
            if (spareSeen.has(key)) {
              return;
            }
            spareSeen.add(key);
            spareLines.push({
              from: name,
              to: target,
              start: startEntry,
              end: endEntry,
            });
          });
        }
      });

      return { points, lines, spareLines };
    },

    setCorridorLayer(data) {
      const map = this.map;
      if (!map) {
        return;
      }
      if (this.corridorLayer && map.getLayer(this.corridorLayer.id)) {
        return;
      }
      const layer = this.createCorridorLayer(data);
      this.corridorLayer = layer;
      map.addLayer(layer);
    },

    ensureCorridorLinkLayer() {
      if (!this.map) {
        return;
      }
      if (this.corridorLinks3dLayer) {
        return;
      }
      const layer = this.createLineLayer3d(
        "corridor-links-3d",
        this.getCorridorColor(this.currentTheme),
        "TRIANGLES",
        HOVER_OUTLINE_COLOR,
      );
      if (layer.setVerticesPerLine) {
        layer.setVerticesPerLine(12);
      } else {
        layer._verticesPerLine = 12;
      }
      this.corridorLinks3dLayer = layer;
      const beforeId = this.map.getLayer("corridor-3d") ? "corridor-3d" : undefined;
      this.map.addLayer(layer, beforeId);
    },

    ensureCorridorSpareLinkLayer() {
      if (!this.map) {
        return;
      }
      if (this.corridorSpareLinks3dLayer) {
        return;
      }
      const layer = this.createLineLayer3d(
        "corridor-spare-links-3d",
        CORRIDOR_SPARE_COLOR,
        "TRIANGLES",
        HOVER_OUTLINE_COLOR,
        CORRIDOR_SPARE_LINK_WIDTH_3D,
        CORRIDOR_SPARE_ALPHA,
      );
      if (layer.setVerticesPerLine) {
        layer.setVerticesPerLine(12);
      } else {
        layer._verticesPerLine = 12;
      }
      this.corridorSpareLinks3dLayer = layer;
      const beforeId = this.map.getLayer("corridor-links-3d")
        ? "corridor-links-3d"
        : undefined;
      this.map.addLayer(layer, beforeId);
    },

    ensureCorridorSpareOpenLayer() {
      if (!this.map) {
        return;
      }
      if (this.corridorSpareOpen3dLayer) {
        return;
      }
      const layer = this.createLineLayer3d(
        "corridor-spare-open-3d",
        this.getCorridorColor(this.currentTheme),
        "TRIANGLES",
        HOVER_OUTLINE_COLOR,
        CORRIDOR_LINK_WIDTH_3D,
      );
      if (layer.setVerticesPerLine) {
        layer.setVerticesPerLine(12);
      } else {
        layer._verticesPerLine = 12;
      }
      this.corridorSpareOpen3dLayer = layer;
      const beforeId = this.map.getLayer("corridor-links-3d")
        ? "corridor-links-3d"
        : undefined;
      this.map.addLayer(layer, beforeId);
    },

    ensureCorridorClosedLayer() {
      if (!this.map) {
        return;
      }
      if (this.corridorClosed3dLayer) {
        return;
      }
      const layer = this.createLineLayer3d(
        "corridor-closed-3d",
        CORRIDOR_CLOSED_COLOR,
        "TRIANGLES",
        null,
        CORRIDOR_CLOSED_LINK_WIDTH_3D,
        0.95,
      );
      if (layer.setVerticesPerLine) {
        layer.setVerticesPerLine(12);
      } else {
        layer._verticesPerLine = 12;
      }
      this.corridorClosed3dLayer = layer;
      this.map.addLayer(layer);
    },

    ensureCorridorLinkPreviewLayer() {
      if (!this.map) {
        return;
      }
      const sourceId = "corridor-link-preview";
      const empty = { type: "FeatureCollection", features: [] };
      if (!this.map.getSource(sourceId)) {
        this.map.addSource(sourceId, { type: "geojson", data: empty });
      }
      if (!this.map.getLayer(sourceId)) {
        this.map.addLayer({
          id: sourceId,
          type: "line",
          source: sourceId,
          layout: { "line-join": "round", "line-cap": "round" },
          paint: {
            "line-color": CORRIDOR_LINK_PREVIEW_COLOR,
            "line-width": CORRIDOR_LINK_PREVIEW_WIDTH,
            "line-opacity": 0.9,
          },
        });
      }
      this.reorderPlanLayers();
    },

    setCorridorLinkPreview(fromName, toName) {
      if (!this.map) {
        return;
      }
      const start = this.corridorPointLookup ? this.corridorPointLookup.get(fromName) : null;
      const end = this.corridorPointLookup ? this.corridorPointLookup.get(toName) : null;
      if (!start || !end) {
        return;
      }
      this.ensureCorridorLinkPreviewLayer();
      const source = this.map.getSource("corridor-link-preview");
      if (!source || !source.setData) {
        return;
      }
      source.setData({
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            geometry: {
              type: "LineString",
              coordinates: [start.coord, end.coord],
            },
            properties: {},
          },
        ],
      });
      this.map.triggerRepaint();
    },

    clearCorridorLinkPreview() {
      if (!this.map || !this.map.getSource("corridor-link-preview")) {
        return;
      }
      this.map.getSource("corridor-link-preview").setData({
        type: "FeatureCollection",
        features: [],
      });
      this.map.triggerRepaint();
    },

    updateCorridorLinks3dLayer(data) {
      if (!this.planLayersReady) {
        this.ensurePlanLayers();
      }
      if (!this.corridorLinks3dLayer || !this.map) {
        return;
      }
      const unitsPerPixel = this.getMercatorUnitsPerPixel();
      if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
        this.scheduleCorridorLinkUpdate();
        return;
      }
      const laneSizing = this.getLinkLaneSizing(CORRIDOR_LINK_WIDTH_3D);
      const positions = [];
      data.lines.forEach((line) => {
        if (!line || !line.start || !line.end) {
          return;
        }
        const startCoord = line.start.coord;
        const endCoord = line.end.coord;
        if (!startCoord || !endCoord) {
          return;
        }
        const altA = line.start.altitude_m ?? CORRIDOR_ALT_M;
        const altB = line.end.altitude_m ?? CORRIDOR_ALT_M;
        const segment = this.buildCrossLinePositions(
          [startCoord, endCoord],
          [altA, altB],
          laneSizing.laneWidth,
        );
        if (segment && segment.length) {
          positions.push(...segment);
        }
      });
      this.corridorLinks3dLayer.updatePositions(positions);
      this.map.triggerRepaint();
    },

    updateCorridorSpareLinks3dLayer(data) {
      if (!this.planLayersReady) {
        this.ensurePlanLayers();
      }
      if (!this.corridorSpareLinks3dLayer || !this.map) {
        return;
      }
      const unitsPerPixel = this.getMercatorUnitsPerPixel();
      if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
        this.scheduleCorridorSpareLinkUpdate();
        return;
      }
      const laneSizing = this.getLinkLaneSizing(CORRIDOR_SPARE_LINK_WIDTH_3D);
      const halfWidth = (laneSizing.laneWidth * unitsPerPixel) / 2;
      const positions = [];
      const dashIndex = [];
      let segmentIndex = 0;
      const dashOn = Math.max(1, CORRIDOR_SPARE_DASH_ON_M);
      const dashOff = Math.max(1, CORRIDOR_SPARE_DASH_OFF_M);
      const dashCycle = dashOn + dashOff;
      const appendSegment = (sx, sy, sz, ex, ey, ez) => {
        if (!halfWidth) {
          return;
        }
        const start = { x: sx, y: sy, z: sz };
        const end = { x: ex, y: ey, z: ez };
        this.appendCrossSegmentPositions(positions, start, end, halfWidth);
      };
      const lines = data && data.spareLines ? data.spareLines : [];
      lines.forEach((line, lineIndex) => {
        const startAlt = line.start.altitude_m ?? CORRIDOR_ALT_M;
        const endAlt = line.end.altitude_m ?? CORRIDOR_ALT_M;
        const startCoord = line.start.coord;
        const endCoord = line.end.coord;
        if (!startCoord || !endCoord) {
          return;
        }
        const start = maplibregl.MercatorCoordinate.fromLngLat(startCoord, startAlt);
        const end = maplibregl.MercatorCoordinate.fromLngLat(endCoord, endAlt);
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const dz = end.z - start.z;
        const length_m = computeDistanceMeters(
          startCoord[0],
          startCoord[1],
          endCoord[0],
          endCoord[1],
        );
        dashIndex[lineIndex] = segmentIndex;
        if (!Number.isFinite(length_m) || length_m <= dashOn) {
          appendSegment(start.x, start.y, start.z, end.x, end.y, end.z);
          segmentIndex += 1;
          return;
        }
        let traveled = 0;
        while (traveled < length_m) {
          const segStart = traveled;
          const segEnd = Math.min(traveled + dashOn, length_m);
          const t0 = segStart / length_m;
          const t1 = segEnd / length_m;
          const sx = start.x + dx * t0;
          const sy = start.y + dy * t0;
          const sz = start.z + dz * t0;
          const ex = start.x + dx * t1;
          const ey = start.y + dy * t1;
          const ez = start.z + dz * t1;
          appendSegment(sx, sy, sz, ex, ey, ez);
          segmentIndex += 1;
          traveled += dashCycle;
        }
      });
      this.corridorSpareLinks3dLayer.updatePositions(positions);
      this.corridorSpareLinkDashIndex = dashIndex;
      this.map.triggerRepaint();
    },

    updateCorridorSpareOpen3dLayer(data) {
      if (!this.planLayersReady) {
        this.ensurePlanLayers();
      }
      if (!this.corridorSpareOpen3dLayer || !this.map) {
        return;
      }
      const unitsPerPixel = this.getMercatorUnitsPerPixel();
      if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
        this.scheduleCorridorSpareOpenUpdate();
        return;
      }
      const laneSizing = this.getLinkLaneSizing(CORRIDOR_LINK_WIDTH_3D);
      const openSet = this.openSpareCorridorEdges;
      const positions = [];
      if (openSet && openSet.size && data && data.spareLines) {
        data.spareLines.forEach((line) => {
          if (!line || !line.start || !line.end) {
            return;
          }
          const key = this.getCorridorEdgeKey(line.from, line.to);
          if (!key || !openSet.has(key)) {
            return;
          }
          const startCoord = line.start.coord;
          const endCoord = line.end.coord;
          if (!startCoord || !endCoord) {
            return;
          }
          const altA = line.start.altitude_m ?? CORRIDOR_ALT_M;
          const altB = line.end.altitude_m ?? CORRIDOR_ALT_M;
          const segment = this.buildCrossLinePositions(
            [startCoord, endCoord],
            [altA, altB],
            laneSizing.laneWidth,
          );
          if (segment && segment.length) {
            positions.push(...segment);
          }
        });
      }
      this.corridorSpareOpen3dLayer.updatePositions(positions);
      this.map.triggerRepaint();
    },

    updateCorridorClosed3dLayer() {
      if (!this.map) {
        return;
      }
      this.ensureCorridorClosedLayer();
      if (!this.corridorClosed3dLayer) {
        return;
      }
      if (!this.corridorData || !this.corridorData.lines) {
        this.corridorClosed3dLayer.updatePositions([]);
        return;
      }
      const unitsPerPixel = this.getMercatorUnitsPerPixel();
      if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
        this.scheduleCorridorClosedUpdate();
        return;
      }
      const laneSizing = this.getLinkLaneSizing(CORRIDOR_CLOSED_LINK_WIDTH_3D);
      const indices = Array.isArray(this.corridorClosedLineIndices)
        ? this.corridorClosedLineIndices
        : [];
      if (!indices.length) {
        this.corridorClosed3dLayer.updatePositions([]);
        this.map.triggerRepaint();
        return;
      }
      const positions = [];
      indices.forEach((index) => {
        const line = this.corridorData.lines[index];
        if (!line || !line.start || !line.end) {
          return;
        }
        const startCoord = line.start.coord;
        const endCoord = line.end.coord;
        if (!startCoord || !endCoord) {
          return;
        }
        const altA = line.start.altitude_m ?? CORRIDOR_ALT_M;
        const altB = line.end.altitude_m ?? CORRIDOR_ALT_M;
        const segment = this.buildCrossLinePositions(
          [startCoord, endCoord],
          [altA, altB],
          laneSizing.laneWidth,
        );
        if (segment && segment.length) {
          positions.push(...segment);
        }
      });
      this.corridorClosed3dLayer.updatePositions(positions);
      this.map.triggerRepaint();
    },

    scheduleCorridorLinkUpdate() {
      if (this.corridorLinkUpdateScheduled) {
        return;
      }
      this.corridorLinkUpdateScheduled = true;
      requestAnimationFrame(() => {
        this.corridorLinkUpdateScheduled = false;
        if (this.corridorData) {
          this.updateCorridorLinks3dLayer(this.corridorData);
        }
      });
    },

    scheduleCorridorSpareLinkUpdate() {
      if (this.corridorSpareLinkUpdateScheduled) {
        return;
      }
      this.corridorSpareLinkUpdateScheduled = true;
      requestAnimationFrame(() => {
        this.corridorSpareLinkUpdateScheduled = false;
        if (this.corridorData) {
          this.updateCorridorSpareLinks3dLayer(this.corridorData);
        }
      });
    },

    scheduleCorridorSpareOpenUpdate() {
      if (this.corridorSpareOpenLinkUpdateScheduled) {
        return;
      }
      this.corridorSpareOpenLinkUpdateScheduled = true;
      requestAnimationFrame(() => {
        this.corridorSpareOpenLinkUpdateScheduled = false;
        if (this.corridorData) {
          this.updateCorridorSpareOpen3dLayer(this.corridorData);
        }
      });
    },

    scheduleCorridorClosedUpdate() {
      if (this.corridorClosedUpdateScheduled) {
        return;
      }
      this.corridorClosedUpdateScheduled = true;
      requestAnimationFrame(() => {
        this.corridorClosedUpdateScheduled = false;
        if (this.corridorData) {
          this.updateCorridorClosed3dLayer();
        }
      });
    },

    setupCorridorLinkResize() {
      if (!this.map || this.corridorLinkResizeBound) {
        return;
      }
      this.corridorLinkResizeBound = true;
      const update = () => this.scheduleCorridorLinkUpdate();
      this.map.on("zoomend", update);
      this.map.on("resize", update);
    },

    setupCorridorSpareLinkResize() {
      if (!this.map || this.corridorSpareLinkResizeBound) {
        return;
      }
      this.corridorSpareLinkResizeBound = true;
      const update = () => this.scheduleCorridorSpareLinkUpdate();
      this.map.on("zoomend", update);
      this.map.on("resize", update);
    },

    setupCorridorSpareOpenResize() {
      if (!this.map || this.corridorSpareOpenLinkResizeBound) {
        return;
      }
      this.corridorSpareOpenLinkResizeBound = true;
      const update = () => this.scheduleCorridorSpareOpenUpdate();
      this.map.on("zoomend", update);
      this.map.on("resize", update);
    },

    setupCorridorClosedResize() {
      if (!this.map || this.corridorClosedResizeBound) {
        return;
      }
      this.corridorClosedResizeBound = true;
      const update = () => this.scheduleCorridorClosedUpdate();
      this.map.on("zoomend", update);
      this.map.on("resize", update);
    },

    buildCorridorBuffers(data) {
      const pointPositions = [];
      const linePositions = [];
      data.points.forEach((entry) => {
        const merc = maplibregl.MercatorCoordinate.fromLngLat(
          entry.coord,
          entry.altitude_m ?? 0,
        );
        pointPositions.push(merc.x, merc.y, merc.z);
      });
      data.lines.forEach((line) => {
        const startAlt = line.start.altitude_m ?? 0;
        const endAlt = line.end.altitude_m ?? 0;
        const start = maplibregl.MercatorCoordinate.fromLngLat(line.start.coord, startAlt);
        const end = maplibregl.MercatorCoordinate.fromLngLat(line.end.coord, endAlt);
        linePositions.push(start.x, start.y, start.z, end.x, end.y, end.z);
      });
      return {
        pointPositions,
        linePositions,
      };
    },

    parseCorridorLinkList(cell) {
      if (!cell) {
        return [];
      }
      return String(cell)
        .split(",")
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0);
    },

    buildCorridorHitData(data) {
      const points = data.points.map((entry, index) => {
        const altitude = entry.altitude_m ?? 0;
        const mercator = maplibregl.MercatorCoordinate.fromLngLat(entry.coord, altitude);
        return {
          index,
          name: entry.name,
          coord: entry.coord,
          altitude_m: altitude,
          mercator,
        };
      });
      const lines = data.lines.map((line, index) => {
        const startAlt = line.start.altitude_m ?? 0;
        const endAlt = line.end.altitude_m ?? 0;
        const mercStart = maplibregl.MercatorCoordinate.fromLngLat(line.start.coord, startAlt);
        const mercEnd = maplibregl.MercatorCoordinate.fromLngLat(line.end.coord, endAlt);
        return {
          index,
          name: `${line.from} - ${line.to}`,
          start: line.start,
          end: line.end,
          mercStart,
          mercEnd,
        };
      });
      return { points, lines };
    },

    buildCorridorSpareHitData(data) {
      if (!data || !data.spareLines || !data.spareLines.length) {
        return { lines: [] };
      }
      const lines = data.spareLines.map((line, index) => {
        const startAlt = line.start.altitude_m ?? 0;
        const endAlt = line.end.altitude_m ?? 0;
        const mercStart = maplibregl.MercatorCoordinate.fromLngLat(line.start.coord, startAlt);
        const mercEnd = maplibregl.MercatorCoordinate.fromLngLat(line.end.coord, endAlt);
        return {
          index,
          name: `${line.from} - ${line.to}`,
          start: line.start,
          end: line.end,
          mercStart,
          mercEnd,
        };
      });
      return { lines };
    },

    buildVertiportLinkHitData(data) {
      const lines = data.lines.map((line, index) => {
        const startAlt = line.start.altitude_m ?? 0;
        const endAlt = line.end.altitude_m ?? 0;
        const mercStart = maplibregl.MercatorCoordinate.fromLngLat(line.start.coord, startAlt);
        const mercEnd = maplibregl.MercatorCoordinate.fromLngLat(line.end.coord, endAlt);
        return {
          index,
          id: line.id ?? index,
          name: `${line.from} - ${line.to}`,
          mercStart,
          mercEnd,
        };
      });
      return { lines };
    },

    projectMercatorToScreen(mercator, matrix) {
      if (!this.map || !mercator || !matrix) {
        return null;
      }
      const x = mercator.x;
      const y = mercator.y;
      const z = mercator.z;
      const w = 1;
      const clipX = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12] * w;
      const clipY = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13] * w;
      const clipW = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15] * w;
      if (!Number.isFinite(clipW) || clipW === 0) {
        return null;
      }
      const ndcX = clipX / clipW;
      const ndcY = clipY / clipW;
      const canvas = this.map.getCanvas();
      const pixelRatio =
        canvas.clientWidth > 0 ? canvas.width / canvas.clientWidth : window.devicePixelRatio || 1;
      const width = canvas.width / pixelRatio;
      const height = canvas.height / pixelRatio;
      return {
        x: (ndcX + 1) * 0.5 * width,
        y: (1 - ndcY) * 0.5 * height,
      };
    },

    distanceToSegment(point, start, end) {
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      if (dx === 0 && dy === 0) {
        return Math.hypot(point.x - start.x, point.y - start.y);
      }
      const t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy);
      const clamped = Math.max(0, Math.min(1, t));
      const projX = start.x + clamped * dx;
      const projY = start.y + clamped * dy;
      return Math.hypot(point.x - projX, point.y - projY);
    },

    findCorridorHoverTarget(pointer, matrix) {
      if (!this.corridorHitData) {
        return null;
      }
      const pointThreshold = 10 * MAP_SIZE_SCALE;
      const lineThreshold = 8 * MAP_SIZE_SCALE;
      let bestPoint = null;
      let bestPointDist = Infinity;
      this.corridorHitData.points.forEach((entry) => {
        const screen = this.projectMercatorToScreen(entry.mercator, matrix);
        if (!screen) {
          return;
        }
        const dist = Math.hypot(pointer.x - screen.x, pointer.y - screen.y);
        if (dist <= pointThreshold && dist < bestPointDist) {
          bestPointDist = dist;
          bestPoint = {
            type: "point",
            index: entry.index,
            name: entry.name,
          };
        }
      });
      if (bestPoint) {
        return bestPoint;
      }
      let bestLine = null;
      let bestLineDist = Infinity;
      this.corridorHitData.lines.forEach((entry) => {
        const start = this.projectMercatorToScreen(entry.mercStart, matrix);
        const end = this.projectMercatorToScreen(entry.mercEnd, matrix);
        if (!start || !end) {
          return;
        }
        const dist = this.distanceToSegment(pointer, start, end);
        if (dist <= lineThreshold && dist < bestLineDist) {
          bestLineDist = dist;
          bestLine = {
            type: "line",
            index: entry.index,
            name: entry.name,
          };
        }
      });
      return bestLine;
    },

    findCorridorSpareHoverTarget(pointer, matrix) {
      if (!this.corridorSpareHitData || !this.corridorSpareHitData.lines) {
        return null;
      }
      if (!matrix) {
        return null;
      }
      const lineThreshold = 8 * MAP_SIZE_SCALE;
      let bestLine = null;
      let bestLineDist = Infinity;
      this.corridorSpareHitData.lines.forEach((entry) => {
        const start = this.projectMercatorToScreen(entry.mercStart, matrix);
        const end = this.projectMercatorToScreen(entry.mercEnd, matrix);
        if (!start || !end) {
          return;
        }
        const dist = this.distanceToSegment(pointer, start, end);
        if (dist <= lineThreshold && dist < bestLineDist) {
          bestLineDist = dist;
          bestLine = {
            type: "line",
            index: entry.index,
            name: entry.name,
            kind: "spare",
          };
        }
      });
      return bestLine;
    },

    findVertiportLinkHoverTarget(pointer, matrix) {
      if (!this.vertiportLinkHitData || !this.vertiportLinkHitData.lines) {
        return null;
      }
      const lineThreshold = 8 * MAP_SIZE_SCALE;
      let bestLine = null;
      let bestLineDist = Infinity;
      this.vertiportLinkHitData.lines.forEach((entry) => {
        const start = this.projectMercatorToScreen(entry.mercStart, matrix);
        const end = this.projectMercatorToScreen(entry.mercEnd, matrix);
        if (!start || !end) {
          return;
        }
        const dist = this.distanceToSegment(pointer, start, end);
        if (dist <= lineThreshold && dist < bestLineDist) {
          bestLineDist = dist;
          bestLine = {
            type: "line",
            index: entry.index,
            id: entry.id,
            name: entry.name,
          };
        }
      });
      return bestLine;
    },

    findTraffic3dHoverTarget(pointer, matrix) {
      if (!this.lastTraffic3dEntries || !this.lastTraffic3dEntries.length) {
        return null;
      }
      const threshold = this.getTrafficHoverThreshold();
      let bestEntry = null;
      let bestDist = Infinity;
      this.lastTraffic3dEntries.forEach((entry) => {
        const altitude = Number(entry.altitude_m) || 0;
        const offset = this.traffic3dIconLayer ? TRAFFIC_ICON_ALTITUDE_OFFSET_M : 0;
        const mercator =
          entry.mercator ||
          maplibregl.MercatorCoordinate.fromLngLat(
            [Number(entry.lon), Number(entry.lat)],
            toTrafficAltitude(altitude + offset),
          );
        if (!mercator) {
          return;
        }
        const screen = this.projectMercatorToScreen(mercator, matrix);
        if (!screen) {
          return;
        }
        const dist = Math.hypot(pointer.x - screen.x, pointer.y - screen.y);
        if (dist <= threshold && dist < bestDist) {
          bestDist = dist;
          bestEntry = entry;
        }
      });
      return bestEntry;
    },

    createCorridorLayer(data) {
      const buffers = this.buildCorridorBuffers(data);
      const color = this.getCorridorColor(this.currentTheme);
      const pointSize = 6 * MAP_SIZE_SCALE * (window.devicePixelRatio || 1);
      const layer = {
        id: "corridor-3d",
        type: "custom",
        renderingMode: "3d",
        _color: color,
        _pointSize: pointSize,
        _hoverPoint: -1,
        _hoverLine: -1,
        _selectedPoint: -1,
        _closedLines: [],
        _highlightColor: HOVER_OUTLINE_COLOR,
        _selectedColor: "#ffb347",
        _hoverPointSize: 6 * MAP_SIZE_SCALE * (window.devicePixelRatio || 1),
        _selectedPointSize: 4 * MAP_SIZE_SCALE * (window.devicePixelRatio || 1),
        _ringWidth: 0.12,
        setColor(nextColor) {
          this._color = nextColor;
        },
        setClosedLines(lines) {
          this._closedLines = Array.isArray(lines) ? lines : [];
        },
        updateBuffers(nextBuffers) {
          this._pendingBuffers = nextBuffers;
          if (!this._gl || !this._pointBuffer || !this._lineBuffer) {
            return;
          }
          const gl = this._gl;
          const pointData = new Float32Array(nextBuffers.pointPositions);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, pointData, gl.STATIC_DRAW);
          this._pointCount = pointData.length / 3;

          const lineData = new Float32Array(nextBuffers.linePositions);
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, lineData, gl.STATIC_DRAW);
          this._lineCount = lineData.length / 3;
          this._pendingBuffers = null;
        },
        setHover(hover) {
          this._hoverPoint = hover && hover.type === "point" ? hover.index : -1;
          this._hoverLine = hover && hover.type === "line" ? hover.index : -1;
        },
        clearHover() {
          this._hoverPoint = -1;
          this._hoverLine = -1;
        },
        setSelectedPoint(index) {
          if (Number.isFinite(index) && index >= 0) {
            this._selectedPoint = index;
          } else {
            this._selectedPoint = -1;
          }
        },
        getMatrix() {
          return this._lastMatrix;
        },
        onAdd(_map, gl) {
          this._gl = gl;
          const vertexSource = `
            attribute vec3 a_pos;
            uniform mat4 u_matrix;
            uniform float u_pointSize;
            void main() {
              gl_Position = u_matrix * vec4(a_pos, 1.0);
              gl_PointSize = u_pointSize;
            }
          `;
          const fragmentSource = `
            precision mediump float;
            uniform vec4 u_color;
            uniform float u_isPoint;
            uniform float u_ring;
            uniform float u_ringWidth;
            void main() {
              if (u_isPoint > 0.5) {
                float dist = length(gl_PointCoord - vec2(0.5));
                if (dist > 0.5) {
                  discard;
                }
                if (u_ring > 0.5) {
                  if (dist < (0.5 - u_ringWidth)) {
                    discard;
                  }
                }
              }
              gl_FragColor = u_color;
            }
          `;
          const compile = (type, source) => {
            const shader = gl.createShader(type);
            gl.shaderSource(shader, source);
            gl.compileShader(shader);
            return shader;
          };
          const vertexShader = compile(gl.VERTEX_SHADER, vertexSource);
          const fragmentShader = compile(gl.FRAGMENT_SHADER, fragmentSource);
          const program = gl.createProgram();
          gl.attachShader(program, vertexShader);
          gl.attachShader(program, fragmentShader);
          gl.linkProgram(program);
          this._program = program;
          this._aPos = gl.getAttribLocation(program, "a_pos");
          this._uMatrix = gl.getUniformLocation(program, "u_matrix");
          this._uColor = gl.getUniformLocation(program, "u_color");
          this._uPointSize = gl.getUniformLocation(program, "u_pointSize");
          this._uIsPoint = gl.getUniformLocation(program, "u_isPoint");
          this._uRing = gl.getUniformLocation(program, "u_ring");
          this._uRingWidth = gl.getUniformLocation(program, "u_ringWidth");

          this._pointBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
          gl.bufferData(
            gl.ARRAY_BUFFER,
            new Float32Array(buffers.pointPositions),
            gl.STATIC_DRAW,
          );
          this._pointCount = buffers.pointPositions.length / 3;

          this._lineBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
          gl.bufferData(
            gl.ARRAY_BUFFER,
            new Float32Array(buffers.linePositions),
            gl.STATIC_DRAW,
          );
          this._lineCount = buffers.linePositions.length / 3;

          if (this._pendingBuffers) {
            this.updateBuffers(this._pendingBuffers);
          }
        },
        render(gl, matrix) {
          if (!this._program) {
            return;
          }
          let drawMatrix = matrix;
          if (
            drawMatrix &&
            typeof drawMatrix.length !== "number" &&
            typeof drawMatrix.toArray === "function"
          ) {
            drawMatrix = drawMatrix.toArray();
          }
          if (!drawMatrix || typeof drawMatrix.length !== "number") {
            return;
          }
          if (!(drawMatrix instanceof Float32Array)) {
            drawMatrix = new Float32Array(drawMatrix);
          }
          this._lastMatrix = drawMatrix;
          gl.useProgram(this._program);
          gl.uniformMatrix4fv(this._uMatrix, false, drawMatrix);
          gl.uniform1f(this._uPointSize, this._pointSize);
          gl.uniform1f(this._uRing, 0);
          gl.uniform1f(this._uRingWidth, this._ringWidth);
          gl.enableVertexAttribArray(this._aPos);
          gl.enable(gl.BLEND);
          gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

          const color = hexToRgba(this._color, 0.95);
          gl.uniform4fv(this._uColor, color);

          if (this._lineCount > 0) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.uniform1f(this._uIsPoint, 0);
            gl.lineWidth(2 * MAP_SIZE_SCALE);
            gl.drawArrays(gl.LINES, 0, this._lineCount);
            if (this._closedLines && this._closedLines.length) {
              gl.uniform4fv(this._uColor, hexToRgba(CORRIDOR_CLOSED_COLOR, 0.95));
              gl.lineWidth(6 * MAP_SIZE_SCALE);
              this._closedLines.forEach((idx) => {
                const offset = idx * 2;
                if (offset + 1 < this._lineCount) {
                  gl.drawArrays(gl.LINES, offset, 2);
                }
              });
              gl.uniform4fv(this._uColor, color);
            }
          }

          if (this._pointCount > 0) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.uniform1f(this._uIsPoint, 1);
            gl.drawArrays(gl.POINTS, 0, this._pointCount);
          }

          const highlightColor = hexToRgba(this._highlightColor, 0.95);
          if (this._hoverLine > -1) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._lineBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.uniform4fv(this._uColor, highlightColor);
            gl.uniform1f(this._uIsPoint, 0);
            gl.uniform1f(this._uRing, 0);
            gl.lineWidth(4 * MAP_SIZE_SCALE);
            gl.drawArrays(gl.LINES, this._hoverLine * 2, 2);
          }

          if (this._hoverPoint > -1) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.uniform4fv(this._uColor, highlightColor);
            gl.uniform1f(this._uIsPoint, 1);
            gl.uniform1f(this._uRing, 1);
            gl.uniform1f(this._uPointSize, this._pointSize + this._hoverPointSize);
            gl.drawArrays(gl.POINTS, this._hoverPoint, 1);
          }

          if (this._selectedPoint > -1 && this._selectedPoint !== this._hoverPoint) {
            gl.bindBuffer(gl.ARRAY_BUFFER, this._pointBuffer);
            gl.vertexAttribPointer(this._aPos, 3, gl.FLOAT, false, 0, 0);
            gl.uniform4fv(this._uColor, hexToRgba(this._selectedColor, 0.95));
            gl.uniform1f(this._uIsPoint, 1);
            gl.uniform1f(this._uRing, 1);
            gl.uniform1f(this._uPointSize, this._pointSize + this._selectedPointSize);
            gl.drawArrays(gl.POINTS, this._selectedPoint, 1);
          }
        },
      };
      return layer;
    },

    setupCorridorHover() {
      if (!this.map) {
        return;
      }
      const label = document.createElement("div");
      label.className = "corridor-hover-label";
      this.map.getContainer().appendChild(label);
      this.corridorHoverLabel = label;

      const coordLabel = document.createElement("div");
      coordLabel.className = "corridor-edit-coord";
      this.map.getContainer().appendChild(coordLabel);
      this.corridorEditCoordLabel = coordLabel;

      this.map.on("mousemove", (event) => this.handleCorridorHover(event));
      this.map.on("mouseleave", () => this.clearCorridorHover());
      this.map.on("movestart", () => this.clearCorridorHover());
      this.map.on("dragstart", () => this.clearCorridorHover());
      this.map.on("zoomstart", () => this.clearCorridorHover());
      this.map.on("pitchstart", () => this.clearCorridorHover());
      this.map.on("rotatestart", () => this.clearCorridorHover());
    },

    setupCorridorCloseClick() {
      if (!this.map) {
        return;
      }
      this.map.on("click", (event) => this.handleCorridorCloseClick(event));
      this.map.on("contextmenu", (event) => this.handleAirspaceEditContextMenu(event));
    },

    handleCorridorCloseClick(event) {
      if (this.handleEmergencyLandingClick && this.handleEmergencyLandingClick(event)) {
        return;
      }
      if (this.handleForceMoveClick && this.handleForceMoveClick(event)) {
        return;
      }
      if (this.handleAirspaceEditClick(event)) {
        return;
      }
      if (this.handleBaseStationEditClick && this.handleBaseStationEditClick(event)) {
        return;
      }
      if (!this.map || !this.corridorLayer || !this.corridorLayer.getMatrix) {
        return;
      }
      if (this.isVertiportEditMode()) {
        return;
      }
      if (this.planState.enabled) {
        return;
      }
      if (this.isTrafficHoverTarget && this.isTrafficHoverTarget(event.point)) {
        return;
      }
      if (this.pickVertiportAt(event.point)) {
        return;
      }
      const matrix = this.corridorLayer.getMatrix();
      if (!matrix) {
        return;
      }
      const target = this.findCorridorHoverTarget(event.point, matrix);
      if (target && target.type === "line") {
        const line =
          this.corridorHitData && this.corridorHitData.lines
            ? this.corridorHitData.lines[target.index]
            : null;
        if (!line || !line.start || !line.end) {
          return;
        }
        this.showCorridorPopup(line, event.lngLat);
        return;
      }
      const spareTarget = this.findCorridorSpareHoverTarget(event.point, matrix);
      if (!spareTarget || spareTarget.type !== "line") {
        return;
      }
      const spareLine =
        this.corridorSpareHitData && this.corridorSpareHitData.lines
          ? this.corridorSpareHitData.lines[spareTarget.index]
          : null;
      if (!spareLine || !spareLine.start || !spareLine.end) {
        return;
      }
      this.showCorridorSparePopup(spareLine, event.lngLat);
    },

    getCorridorEdgeKey(a, b) {
      if (!a || !b) {
        return "";
      }
      return [String(a), String(b)].sort().join("|");
    },

    showCorridorPopup(line, lngLat) {
      if (!this.map) {
        return;
      }
      const fromName = line.start && line.start.name ? String(line.start.name) : "";
      const toName = line.end && line.end.name ? String(line.end.name) : "";
      if (!fromName || !toName) {
        return;
      }
      const key = this.getCorridorEdgeKey(fromName, toName);
      if (!key) {
        return;
      }
      if (
        this.corridorPopupEdge &&
        this.corridorPopupEdge.key === key &&
        this.corridorPopupEdge.kind === "normal"
      ) {
        this.hideCorridorPopup();
        return;
      }
      const isClosed = this.closedCorridorEdges.has(key);
      const scheduleOpen = this.getCorridorScheduleEntry("normal", key, "open");
      const scheduleClose = this.getCorridorScheduleEntry("normal", key, "close");
      if (!this.corridorPopup) {
        this.corridorPopup = new maplibregl.Popup({
          closeButton: true,
          closeOnClick: true,
          className: "corridor-popup",
        });
        if (this.corridorPopup.on) {
          this.corridorPopup.on("close", () => {
            this.corridorPopupEdge = null;
          });
        }
      }
      this.corridorPopupEdge = { key, fromName, toName, kind: "normal" };
      this.corridorPopup
        .setLngLat(lngLat)
        .setDOMContent(
          this.buildCorridorPopupContent({
            name: `${fromName} - ${toName}`,
            isClosed,
            onToggle: () => {
              this.setCorridorClosure(fromName, toName, !isClosed);
              this.hideCorridorPopup();
            },
            onTimedToggle: (durationMs) => {
              const openNow = Boolean(isClosed);
              this.scheduleCorridorTimedChange({
                fromName,
                toName,
                kind: "normal",
                openNow,
                durationMs,
              });
              this.hideCorridorPopup();
            },
            scheduleOpen,
            scheduleClose,
            onScheduleOpen: ({ enabled, startMin, endMin }) => {
              this.setCorridorSchedule({
                fromName,
                toName,
                kind: "normal",
                mode: "open",
                startMin,
                endMin,
                enabled,
              });
              this.hideCorridorPopup();
            },
            onScheduleClose: ({ enabled, startMin, endMin }) => {
              this.setCorridorSchedule({
                fromName,
                toName,
                kind: "normal",
                mode: "close",
                startMin,
                endMin,
                enabled,
              });
              this.hideCorridorPopup();
            },
            onCancel: () => this.hideCorridorPopup(),
          }),
        )
        .addTo(this.map);
    },

    showCorridorSparePopup(line, lngLat) {
      if (!this.map) {
        return;
      }
      const fromName = line.start && line.start.name ? String(line.start.name) : "";
      const toName = line.end && line.end.name ? String(line.end.name) : "";
      if (!fromName || !toName) {
        return;
      }
      const key = this.getCorridorEdgeKey(fromName, toName);
      if (!key) {
        return;
      }
      if (
        this.corridorPopupEdge &&
        this.corridorPopupEdge.key === key &&
        this.corridorPopupEdge.kind === "spare"
      ) {
        this.hideCorridorPopup();
        return;
      }
      const isOpen = this.openSpareCorridorEdges
        ? this.openSpareCorridorEdges.has(key)
        : false;
      const scheduleOpen = this.getCorridorScheduleEntry("spare", key, "open");
      const scheduleClose = this.getCorridorScheduleEntry("spare", key, "close");
      if (!this.corridorPopup) {
        this.corridorPopup = new maplibregl.Popup({
          closeButton: true,
          closeOnClick: true,
          className: "corridor-popup",
        });
        if (this.corridorPopup.on) {
          this.corridorPopup.on("close", () => {
            this.corridorPopupEdge = null;
          });
        }
      }
      this.corridorPopupEdge = { key, fromName, toName, kind: "spare" };
      this.corridorPopup
        .setLngLat(lngLat)
        .setDOMContent(
          this.buildCorridorPopupContent({
            name: `Spare: ${fromName} - ${toName}`,
            isClosed: !isOpen,
            openLabel: "Open",
            closeLabel: "Close",
            onToggle: () => {
              this.setSpareCorridorOpen(fromName, toName, !isOpen);
              this.hideCorridorPopup();
            },
            onTimedToggle: (durationMs) => {
              const openNow = !isOpen;
              this.scheduleCorridorTimedChange({
                fromName,
                toName,
                kind: "spare",
                openNow,
                durationMs,
              });
              this.hideCorridorPopup();
            },
            scheduleOpen,
            scheduleClose,
            onScheduleOpen: ({ enabled, startMin, endMin }) => {
              this.setCorridorSchedule({
                fromName,
                toName,
                kind: "spare",
                mode: "open",
                startMin,
                endMin,
                enabled,
              });
              this.hideCorridorPopup();
            },
            onScheduleClose: ({ enabled, startMin, endMin }) => {
              this.setCorridorSchedule({
                fromName,
                toName,
                kind: "spare",
                mode: "close",
                startMin,
                endMin,
                enabled,
              });
              this.hideCorridorPopup();
            },
            onCancel: () => this.hideCorridorPopup(),
          }),
        )
        .addTo(this.map);
    },

    hideCorridorPopup() {
      if (this.corridorPopup) {
        this.corridorPopup.remove();
      }
      this.corridorPopupEdge = null;
    },

    buildCorridorPopupContent({
      name,
      isClosed,
      onToggle,
      onCancel,
      openLabel,
      closeLabel,
      statusOpenLabel,
      statusClosedLabel,
      onTimedToggle,
      scheduleOpen,
      scheduleClose,
      onScheduleOpen,
      onScheduleClose,
    }) {
      const card = document.createElement("div");
      card.className = "corridor-card";

      const title = document.createElement("div");
      title.className = "corridor-card-title";
      title.textContent = name || "Corridor";
      card.appendChild(title);

      const status = document.createElement("div");
      status.className = "corridor-card-status";
      const openText = statusOpenLabel || "Status: Open";
      const closedText = statusClosedLabel || "Status: Closed";
      status.textContent = isClosed ? closedText : openText;
      card.appendChild(status);

      const actions = document.createElement("div");
      actions.className = "corridor-card-actions";

      const toggle = document.createElement("button");
      toggle.className = "corridor-card-btn";
      toggle.classList.add(isClosed ? "is-open" : "is-close");
      const reopenText = openLabel || "Reopen";
      const closeText = closeLabel || "Close";
      toggle.textContent = isClosed ? reopenText : closeText;
      toggle.addEventListener("click", () => {
        if (typeof onToggle === "function") {
          onToggle();
        }
      });
      actions.appendChild(toggle);

      const cancel = document.createElement("button");
      cancel.className = "corridor-card-btn";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => {
        if (typeof onCancel === "function") {
          onCancel();
        }
      });
      actions.appendChild(cancel);

      card.appendChild(actions);

      if (typeof onTimedToggle === "function") {
        const timer = document.createElement("div");
        timer.className = "corridor-card-timer";

        const actionLabel = document.createElement("span");
        actionLabel.className = "corridor-card-timer-label";
        actionLabel.textContent = isClosed ? (openLabel || "Open") : (closeLabel || "Close");
        timer.appendChild(actionLabel);

        const durationInput = document.createElement("input");
        durationInput.className = "corridor-card-input";
        durationInput.type = "number";
        durationInput.min = "1";
        durationInput.max = "1440";
        durationInput.step = "1";
        durationInput.value = "10";
        timer.appendChild(durationInput);

        const unitSelect = document.createElement("select");
        unitSelect.className = "corridor-card-select";
        const optMin = document.createElement("option");
        optMin.value = "min";
        optMin.textContent = "min";
        const optHour = document.createElement("option");
        optHour.value = "hour";
        optHour.textContent = "hour";
        unitSelect.appendChild(optMin);
        unitSelect.appendChild(optHour);
        timer.appendChild(unitSelect);

        const applyBtn = document.createElement("button");
        applyBtn.className = "corridor-card-btn corridor-card-btn-ghost";
        applyBtn.textContent = "Apply";
        applyBtn.addEventListener("click", () => {
          const raw = Number(durationInput.value);
          if (!Number.isFinite(raw) || raw <= 0) {
            return;
          }
          const unit = unitSelect.value === "hour" ? "hour" : "min";
          const minutes = unit === "hour" ? raw * 60 : raw;
          const durationMs = minutes * 60000;
          onTimedToggle(durationMs, { unit, value: raw, minutes });
        });
        timer.appendChild(applyBtn);

        card.appendChild(timer);
      }

      if (typeof onScheduleOpen === "function") {
        const scheduleWrap = document.createElement("div");
        scheduleWrap.className = "corridor-card-timer corridor-card-schedule";

        const scheduleLabel = document.createElement("span");
        scheduleLabel.className = "corridor-card-timer-label";
        scheduleLabel.textContent = "\uC5F4\uAE30 \uC608\uC57D";
        scheduleWrap.appendChild(scheduleLabel);

        const nowMin = this.getSimMinutesOfDay(this.lastSimTime_s);
        const defaultStart = this.formatClockMinutes(nowMin + 10);
        const defaultEnd = this.formatClockMinutes(nowMin + 40);
        const startInput = document.createElement("input");
        startInput.className = "corridor-card-input corridor-card-input-time";
        startInput.type = "time";
        startInput.step = "60";
        startInput.value =
            scheduleOpen && Number.isFinite(scheduleOpen.startMin)
              ? this.formatClockMinutes(scheduleOpen.startMin)
              : defaultStart;
        const inputsRow = document.createElement("div");
        inputsRow.className = "corridor-card-schedule-row";
        const startTag = document.createElement("span");
        startTag.className = "corridor-card-schedule-tag";
        startTag.textContent = "\uC2DC\uC791";
        inputsRow.appendChild(startTag);
        inputsRow.appendChild(startInput);

        const endInput = document.createElement("input");
        endInput.className = "corridor-card-input corridor-card-input-time";
        endInput.type = "time";
        endInput.step = "60";
        endInput.value =
            scheduleOpen && Number.isFinite(scheduleOpen.endMin)
              ? this.formatClockMinutes(scheduleOpen.endMin)
              : defaultEnd;
        const endTag = document.createElement("span");
        endTag.className = "corridor-card-schedule-tag";
        endTag.textContent = "\uC885\uB8CC";
        inputsRow.appendChild(endTag);
        inputsRow.appendChild(endInput);
        scheduleWrap.appendChild(inputsRow);

          const stopMapGestures = (event) => {
            if (event && typeof event.stopPropagation === "function") {
              event.stopPropagation();
            }
          };
          const clampTimeValue = (input) => {
            if (!input) {
              return;
            }
            const value = String(input.value || "");
            if (!value || value.indexOf(":") < 0) {
              return;
            }
            const [hRaw, mRaw] = value.split(":");
            let hours = Number.parseInt(hRaw, 10);
            let minutes = Number.parseInt(mRaw, 10);
            if (!Number.isFinite(hours)) {
              hours = 0;
            }
            if (!Number.isFinite(minutes)) {
              minutes = 0;
            }
            hours = ((hours % 24) + 24) % 24;
            minutes = ((minutes % 60) + 60) % 60;
            input.value = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
          };
          const adjustTimeByMinutes = (input, delta) => {
            if (!input) {
              return;
            }
            const current = this.parseClockMinutes(input.value);
            const base = Number.isFinite(current) ? current : 0;
            const next = base + delta;
            input.value = this.formatClockMinutes(next);
          };
          const bindTimeInput = (input) => {
            ["mousedown", "dblclick", "touchstart", "touchmove"].forEach((evt) => {
              input.addEventListener(evt, stopMapGestures, { passive: true });
            });
            input.addEventListener("wheel", (event) => {
              stopMapGestures(event);
              if (event && typeof event.preventDefault === "function") {
                event.preventDefault();
              }
              const delta = event && event.deltaY != null ? event.deltaY : 0;
              const step = event && event.shiftKey ? 10 : 1;
              const direction = delta < 0 ? 1 : -1;
              adjustTimeByMinutes(input, direction * step);
            });
            input.addEventListener("change", () => clampTimeValue(input));
            input.addEventListener("blur", () => clampTimeValue(input));
          };
          bindTimeInput(startInput);
          bindTimeInput(endInput);

        const scheduleBtn = document.createElement("button");
        scheduleBtn.className = "corridor-card-btn corridor-card-btn-ghost";
        const isActive = Boolean(scheduleOpen && scheduleOpen.enabled);
        if (isActive) {
          scheduleBtn.classList.add("is-active");
          scheduleBtn.setAttribute("aria-pressed", "true");
        } else {
          scheduleBtn.setAttribute("aria-pressed", "false");
        }
        scheduleBtn.textContent = isActive ? "\uC608\uC57D\uC911" : "\uC608\uC57D";
        scheduleBtn.addEventListener("click", () => {
          const startMin = this.parseClockMinutes(startInput.value);
          const endMin = this.parseClockMinutes(endInput.value);
          if (!Number.isFinite(startMin) || !Number.isFinite(endMin)) {
            return;
          }
          onScheduleOpen({ enabled: true, startMin, endMin });
        });
        const actionRow = document.createElement("div");
        actionRow.className = "corridor-card-schedule-actions";
        actionRow.appendChild(scheduleBtn);

        if (isActive) {
          const clearBtn = document.createElement("button");
          clearBtn.className = "corridor-card-btn corridor-card-btn-ghost";
          clearBtn.textContent = "\uD574\uC81C";
          clearBtn.addEventListener("click", () => {
            onScheduleOpen({ enabled: false });
          });
          actionRow.appendChild(clearBtn);
        }

        scheduleWrap.appendChild(actionRow);
        card.appendChild(scheduleWrap);
      }

      if (typeof onScheduleClose === "function") {
        const scheduleWrap = document.createElement("div");
        scheduleWrap.className = "corridor-card-timer corridor-card-schedule";

        const scheduleLabel = document.createElement("span");
        scheduleLabel.className = "corridor-card-timer-label";
        scheduleLabel.textContent = "\uB2EB\uAE30 \uC608\uC57D";
        scheduleWrap.appendChild(scheduleLabel);

        const nowMin = this.getSimMinutesOfDay(this.lastSimTime_s);
        const defaultStart = this.formatClockMinutes(nowMin + 10);
        const defaultEnd = this.formatClockMinutes(nowMin + 40);
        const startInput = document.createElement("input");
        startInput.className = "corridor-card-input corridor-card-input-time";
        startInput.type = "time";
        startInput.step = "60";
        startInput.value =
            scheduleClose && Number.isFinite(scheduleClose.startMin)
              ? this.formatClockMinutes(scheduleClose.startMin)
              : defaultStart;
        const inputsRow = document.createElement("div");
        inputsRow.className = "corridor-card-schedule-row";
        const startTag = document.createElement("span");
        startTag.className = "corridor-card-schedule-tag";
        startTag.textContent = "\uC2DC\uC791";
        inputsRow.appendChild(startTag);
        inputsRow.appendChild(startInput);

        const endInput = document.createElement("input");
        endInput.className = "corridor-card-input corridor-card-input-time";
        endInput.type = "time";
        endInput.step = "60";
        endInput.value =
            scheduleClose && Number.isFinite(scheduleClose.endMin)
              ? this.formatClockMinutes(scheduleClose.endMin)
              : defaultEnd;
        const endTag = document.createElement("span");
        endTag.className = "corridor-card-schedule-tag";
        endTag.textContent = "\uC885\uB8CC";
        inputsRow.appendChild(endTag);
        inputsRow.appendChild(endInput);
        scheduleWrap.appendChild(inputsRow);

        const stopMapGestures = (event) => {
          if (event && typeof event.stopPropagation === "function") {
            event.stopPropagation();
          }
        };
        const clampTimeValue = (input) => {
          if (!input) {
            return;
          }
          const value = String(input.value || "");
          if (!value || value.indexOf(":") < 0) {
            return;
          }
          const [hRaw, mRaw] = value.split(":");
          let hours = Number.parseInt(hRaw, 10);
          let minutes = Number.parseInt(mRaw, 10);
          if (!Number.isFinite(hours)) {
            hours = 0;
          }
          if (!Number.isFinite(minutes)) {
            minutes = 0;
          }
          hours = ((hours % 24) + 24) % 24;
          minutes = ((minutes % 60) + 60) % 60;
          input.value = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
        };
        const adjustTimeByMinutes = (input, delta) => {
          if (!input) {
            return;
          }
          const current = this.parseClockMinutes(input.value);
          const base = Number.isFinite(current) ? current : 0;
          const next = base + delta;
          input.value = this.formatClockMinutes(next);
        };
        const bindTimeInput = (input) => {
          ["mousedown", "dblclick", "touchstart", "touchmove"].forEach((evt) => {
            input.addEventListener(evt, stopMapGestures, { passive: true });
          });
          input.addEventListener("wheel", (event) => {
            stopMapGestures(event);
            if (event && typeof event.preventDefault === "function") {
              event.preventDefault();
            }
            const delta = event && event.deltaY != null ? event.deltaY : 0;
            const step = event && event.shiftKey ? 10 : 1;
            const direction = delta < 0 ? 1 : -1;
            adjustTimeByMinutes(input, direction * step);
          });
          input.addEventListener("change", () => clampTimeValue(input));
          input.addEventListener("blur", () => clampTimeValue(input));
        };
        bindTimeInput(startInput);
        bindTimeInput(endInput);

        const scheduleBtn = document.createElement("button");
        scheduleBtn.className = "corridor-card-btn corridor-card-btn-ghost";
        const isActive = Boolean(scheduleClose && scheduleClose.enabled);
        if (isActive) {
          scheduleBtn.classList.add("is-active");
          scheduleBtn.setAttribute("aria-pressed", "true");
        } else {
          scheduleBtn.setAttribute("aria-pressed", "false");
        }
        scheduleBtn.textContent = isActive ? "\uC608\uC57D\uC911" : "\uC608\uC57D";
        scheduleBtn.addEventListener("click", () => {
          const startMin = this.parseClockMinutes(startInput.value);
          const endMin = this.parseClockMinutes(endInput.value);
          if (!Number.isFinite(startMin) || !Number.isFinite(endMin)) {
            return;
          }
          onScheduleClose({ enabled: true, startMin, endMin });
        });
        const actionRow = document.createElement("div");
        actionRow.className = "corridor-card-schedule-actions";
        actionRow.appendChild(scheduleBtn);

        if (isActive) {
          const clearBtn = document.createElement("button");
          clearBtn.className = "corridor-card-btn corridor-card-btn-ghost";
          clearBtn.textContent = "\uD574\uC81C";
          clearBtn.addEventListener("click", () => {
            onScheduleClose({ enabled: false });
          });
          actionRow.appendChild(clearBtn);
        }

        scheduleWrap.appendChild(actionRow);
        card.appendChild(scheduleWrap);
      }

      if (scheduleOpen || scheduleClose) {
        const scheduleSummary = document.createElement("div");
        scheduleSummary.className = "corridor-card-schedule-table";

        const title = document.createElement("div");
        title.className = "corridor-card-schedule-title";
        title.textContent = "\uC608\uC57D \uD45C";
        scheduleSummary.appendChild(title);

        const table = document.createElement("div");
        table.className = "corridor-card-schedule-grid";

        const addRow = (label, entry) => {
          const row = document.createElement("div");
          row.className = "corridor-card-schedule-row";

          const nameCell = document.createElement("div");
          nameCell.className = "corridor-card-schedule-cell corridor-card-schedule-name";
          nameCell.textContent = label;
          row.appendChild(nameCell);

          const timeCell = document.createElement("div");
          timeCell.className = "corridor-card-schedule-cell corridor-card-schedule-time";
          if (entry && entry.enabled && Number.isFinite(entry.startMin) && Number.isFinite(entry.endMin)) {
            timeCell.textContent = `${this.formatClockMinutes(entry.startMin)} ~ ${this.formatClockMinutes(entry.endMin)}`;
          } else {
            timeCell.textContent = "-";
          }
          row.appendChild(timeCell);

          const statusCell = document.createElement("div");
          statusCell.className = "corridor-card-schedule-cell corridor-card-schedule-status";
          statusCell.textContent = entry && entry.enabled ? "\uC628" : "\uC624\uD504";
          row.appendChild(statusCell);

          table.appendChild(row);
        };

        addRow("\uAC1C\uBC29 \uC608\uC57D", scheduleOpen);
        addRow("\uD3D0\uC1C4 \uC608\uC57D", scheduleClose);

        scheduleSummary.appendChild(table);
        card.appendChild(scheduleSummary);
      }

      return card;
    },

    ensureCorridorTimedActions() {
      if (!this.corridorTimedActions) {
        this.corridorTimedActions = new Map();
      }
      return this.corridorTimedActions;
    },

      clearCorridorTimedChange(kind, key, options = {}) {
        if (!key) {
          return;
        }
        const map = this.corridorTimedActions;
      if (!map || !(map instanceof Map)) {
        return;
      }
      const timerKey = `${kind}:${key}`;
      const entry = map.get(timerKey);
      if (entry && entry.timer) {
        clearTimeout(entry.timer);
      }
      map.delete(timerKey);
        if (!options.silent && entry && Number.isFinite(entry.untilSim_s)) {
          this.addStatusMessage({
            text: `Timed ${kind === "spare" ? "spare" : "corridor"} action cleared.`,
            level: "info",
            ttlMs: 2000,
          });
        }
        this.updateCorridorTimedLabels(this.lastSimTime_s);
      },

      formatCorridorCountdown(seconds) {
        const total = Math.max(0, Math.ceil(Number(seconds) || 0));
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const secs = total % 60;
        if (hours > 0) {
          return `${hours}:${String(minutes).padStart(2, "0")}`;
        }
        return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
      },

      formatClockMinutes(value) {
        const total = Number.isFinite(value) ? Math.round(value) : 0;
        const safe = ((total % 1440) + 1440) % 1440;
        const hours = Math.floor(safe / 60);
        const minutes = safe % 60;
        return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
      },

      parseClockMinutes(value) {
        const text = String(value || "").trim();
        if (!text) {
          return null;
        }
        const parts = text.split(":");
        if (parts.length < 2) {
          return null;
        }
        const hours = Number.parseInt(parts[0], 10);
        const minutes = Number.parseInt(parts[1], 10);
        if (!Number.isFinite(hours) || !Number.isFinite(minutes)) {
          return null;
        }
        if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
          return null;
        }
        return hours * 60 + minutes;
      },

      getSimMinutesOfDay(simTime_s) {
        const base = Number.isFinite(simTime_s)
          ? simTime_s
          : Number.isFinite(this.lastSimTime_s)
            ? this.lastSimTime_s
            : 0;
        const startMin = this.getOperationMinutes ? this.getOperationMinutes().startMin : 0;
        const offset = Number.isFinite(startMin) ? startMin * 60 : 0;
        const totalMinutes = (base + offset) / 60;
        return ((totalMinutes % 1440) + 1440) % 1440;
      },

      isScheduleOpen(nowMin, startMin, endMin) {
        if (!Number.isFinite(nowMin) || !Number.isFinite(startMin) || !Number.isFinite(endMin)) {
          return false;
        }
        if (startMin == endMin) {
          return true;
        }
        if (startMin < endMin) {
          return nowMin >= startMin && nowMin < endMin;
        }
        return nowMin >= startMin || nowMin < endMin;
      },

      minutesUntil(nowMin, targetMin) {
        if (!Number.isFinite(nowMin) || !Number.isFinite(targetMin)) {
          return 0;
        }
        let diff = targetMin - nowMin;
        if (diff < 0) {
          diff += 1440;
        }
        return diff;
      },

      formatHourMinuteLabel(minutes) {
        const total = Math.max(0, Math.ceil(Number(minutes) || 0));
        const hours = Math.floor(total / 60);
        const mins = total % 60;
        return `${String(hours).padStart(2, "0")}\uC2DC\uAC04 ${String(mins).padStart(2, "0")}\uBD84`;
      },

      getZoomScale(zoom, options = {}) {
        const minZoom = Number.isFinite(options.minZoom) ? options.minZoom : 6;
        const maxZoom = Number.isFinite(options.maxZoom) ? options.maxZoom : 12;
        const minScale = Number.isFinite(options.minScale) ? options.minScale : 0.5;
        const maxScale = Number.isFinite(options.maxScale) ? options.maxScale : 1;
        if (!Number.isFinite(zoom)) {
          return maxScale;
        }
        if (zoom <= minZoom) {
          return minScale;
        }
        if (zoom >= maxZoom) {
          return maxScale;
        }
        const t = (zoom - minZoom) / (maxZoom - minZoom);
        return minScale + t * (maxScale - minScale);
      },

      ensureCorridorSchedules() {
        if (!this.corridorSchedules) {
          this.corridorSchedules = new Map();
        }
        return this.corridorSchedules;
      },

      getCorridorScheduleEntry(kind, key, mode) {
        if (!key) {
          return null;
        }
        const map = this.corridorSchedules;
        if (!map || !(map instanceof Map)) {
          return null;
        }
        const scheduleKey = `${kind}:${key}:${mode || "open"}`;
        return map.get(scheduleKey) || null;
      },

      setCorridorSchedule({ fromName, toName, kind, mode, startMin, endMin, enabled }) {
        const key = this.getCorridorEdgeKey(fromName, toName);
        if (!key) {
          return;
        }
        const scheduleMode = mode || "open";
        const scheduleKey = `${kind}:${key}:${scheduleMode}`;
        const map = this.ensureCorridorSchedules();
        if (!enabled) {
          map.delete(scheduleKey);
          this.updateCorridorTimedLabels(this.lastSimTime_s);
          return;
        }
        const start = Number(startMin);
        const end = Number(endMin);
        if (!Number.isFinite(start) || !Number.isFinite(end)) {
          return;
        }
        const entry = {
          kind: kind || "normal",
          mode: scheduleMode,
          fromName,
          toName,
          startMin: ((start % 1440) + 1440) % 1440,
          endMin: ((end % 1440) + 1440) % 1440,
          enabled: true,
          lastInWindow: null,
          prevOpenState: null,
        };
        const prev = map.get(scheduleKey);
        if (prev) {
          if (typeof prev.lastInWindow !== "undefined") {
            entry.lastInWindow = prev.lastInWindow;
          }
          if (typeof prev.prevOpenState === "boolean") {
            entry.prevOpenState = prev.prevOpenState;
          }
        }
        map.set(scheduleKey, entry);
        if (typeof this.clearCorridorTimedChange === "function") {
          this.clearCorridorTimedChange(kind, key, { silent: true });
        }
        if (typeof this.applyCorridorSchedules === "function") {
          this.applyCorridorSchedules(this.lastSimTime_s, { force: true });
        }
        this.updateCorridorTimedLabels(this.lastSimTime_s);
      },

      applyCorridorSchedules(simTime_s, options = {}) {
        const map = this.corridorSchedules;
        if (!map || !(map instanceof Map) || map.size === 0) {
          return;
        }
        const nowMin = this.getSimMinutesOfDay(simTime_s);
        map.forEach((entry) => {
          if (!entry || !entry.enabled) {
            return;
          }
          const inWindow = this.isScheduleOpen(nowMin, entry.startMin, entry.endMin);
          const wasInWindow = entry.lastInWindow;
          if (wasInWindow == null) {
            entry.lastInWindow = inWindow;
            if (!inWindow || !options.force) {
              return;
            }
          } else if (inWindow === wasInWindow) {
            return;
          }
          const key = this.getCorridorEdgeKey(entry.fromName, entry.toName);
          if (!key) {
            entry.lastInWindow = inWindow;
            return;
          }
          const isOpenNow =
            entry.kind === "spare"
              ? this.openSpareCorridorEdges && this.openSpareCorridorEdges.has(key)
              : !this.closedCorridorEdges.has(key);
          const setOpenState = (open) => {
            if (entry.kind === "spare") {
              this.setSpareCorridorOpen(entry.fromName, entry.toName, open, {
                skipTimedClear: true,
              });
            } else {
              this.setCorridorClosure(entry.fromName, entry.toName, !open, {
                skipTimedClear: true,
              });
            }
          };
          if (inWindow) {
            entry.prevOpenState = isOpenNow;
            if (entry.mode === "close") {
              setOpenState(false);
            } else {
              setOpenState(true);
            }
          } else if (typeof entry.prevOpenState === "boolean") {
            setOpenState(entry.prevOpenState);
          }
          entry.lastInWindow = inWindow;
        });
      },


      updateCorridorTimedLabels(simTime_s) {
        if (!this.map) {
          return;
        }
        this.ensureCorridorTimerLabelLayer();
        const source = this.map.getSource && this.map.getSource("corridor-timer-labels");
        if (!source || typeof source.setData !== "function") {
          return;
        }
        const timedMap = this.corridorTimedActions;
        const scheduleMap = this.corridorSchedules;
        const hasTimed = timedMap && timedMap instanceof Map && timedMap.size > 0;
        const hasSchedule = scheduleMap && scheduleMap instanceof Map && scheduleMap.size > 0;
        if (!hasTimed && !hasSchedule) {
          if (this.corridorTimedLabelsNonEmpty) {
            source.setData({ type: "FeatureCollection", features: [] });
            this.corridorTimedLabelsNonEmpty = false;
          }
          this.updateCorridorScheduleMarkers([]);
          return;
        }
        const nowSec =
          Number.isFinite(simTime_s) && simTime_s >= 0
            ? Number(simTime_s)
            : Number.isFinite(this.lastSimTime_s)
              ? this.lastSimTime_s
              : 0;
        const nowMin = this.getSimMinutesOfDay(nowSec);
        const features = [];
        const resolveLineMidpoint = (entry) => {
          if (!entry) {
            return null;
          }
          const key = this.getCorridorEdgeKey(entry.fromName, entry.toName);
          const lineMap =
            entry.kind === "spare" ? this.corridorSpareLineByKey : this.corridorLineByKey;
          const line = lineMap && key ? lineMap.get(key) : null;
          if (line && line.start && line.end && line.start.coord && line.end.coord) {
            const mid = [
              (line.start.coord[0] + line.end.coord[0]) / 2,
              (line.start.coord[1] + line.end.coord[1]) / 2,
            ];
            return { mid, startCoord: line.start.coord, endCoord: line.end.coord };
          }
          const start =
            (this.corridorPointLookup && this.corridorPointLookup.get(entry.fromName)) ||
            (this.vertiportPointLookup && this.vertiportPointLookup.get(entry.fromName));
          const end =
            (this.corridorPointLookup && this.corridorPointLookup.get(entry.toName)) ||
            (this.vertiportPointLookup && this.vertiportPointLookup.get(entry.toName));
          if (!start || !end || !start.coord || !end.coord) {
            return null;
          }
          const mid = [
            (start.coord[0] + end.coord[0]) / 2,
            (start.coord[1] + end.coord[1]) / 2,
          ];
          return { mid, startCoord: start.coord, endCoord: end.coord };
        };
        const scheduledKeys = new Set();
        if (hasSchedule) {
          scheduleMap.forEach((entry) => {
            if (!entry || !entry.enabled) {
              return;
            }
            const key = this.getCorridorEdgeKey(entry.fromName, entry.toName);
            if (!key) {
              return;
            }
            const baseKey = `${entry.kind || "normal"}:${key}`;
            scheduledKeys.add(baseKey);
            const info = resolveLineMidpoint(entry);
            if (!info) {
              return;
            }
            const untilStart = this.minutesUntil(nowMin, entry.startMin);
            const untilEnd = this.minutesUntil(nowMin, entry.endMin);
            const isClose = entry.mode === "close";
            const label = isClose
              ? `항로 폐쇄 예약 중 (-${this.formatHourMinuteLabel(untilStart)})
재개까지 ${this.formatHourMinuteLabel(untilEnd)}`
              : `항로 개방 예약 중 (-${this.formatHourMinuteLabel(untilStart)})
폐쇄까지 ${this.formatHourMinuteLabel(untilEnd)}`;
            const markerColor = isClose ? "#f87171" : "#34d399";
            const badge = isClose ? "\uB2EB" : "\uC5F4";
            features.push({
              type: "Feature",
              geometry: { type: "Point", coordinates: info.mid },
              properties: {
                label,
                remaining: untilEnd,
                kind: entry.kind || "normal",
                markerColor,
                badge,
                markerId: `${entry.kind || "normal"}:${key}:${entry.mode || "open"}`,
                startCoord: info.startCoord,
                endCoord: info.endCoord,
              },
            });
          });
        }
        if (hasTimed) {
          timedMap.forEach((entry) => {
            if (!entry || !Number.isFinite(entry.untilSim_s)) {
              return;
            }
            const remaining = entry.untilSim_s - nowSec;
            if (remaining <= 0) {
              return;
            }
            const key = this.getCorridorEdgeKey(entry.fromName, entry.toName);
            if (!key) {
              return;
            }
            const baseKey = `${entry.kind || "normal"}:${key}`;
            if (scheduledKeys.has(baseKey)) {
              return;
            }
            const info = resolveLineMidpoint(entry);
            if (!info) {
              return;
            }
            features.push({
              type: "Feature",
              geometry: { type: "Point", coordinates: info.mid },
              properties: {
                label: `임시 상태 종료까지 ${this.formatCorridorCountdown(remaining)}`,
                remaining,
                kind: entry.kind || "normal",
                markerColor: "#94a3b8",
                badge: "\uC784",
                markerId: `${entry.kind || "normal"}:${key}:timed`,
                startCoord: info.startCoord,
                endCoord: info.endCoord,
              },
            });
          });
        }
        source.setData({ type: "FeatureCollection", features });
        this.corridorTimedLabelsNonEmpty = features.length > 0;
        this.updateCorridorScheduleMarkers(features);
      },

      updateCorridorScheduleMarkers(features) {
        if (!this.map) {
          return;
        }
        if (!this.corridorScheduleMarkers) {
          this.corridorScheduleMarkers = new Map();
        }
        const next = new Map();
        const map = this.map;
        const zoom = map.getZoom ? map.getZoom() : 12;
        const scale = this.getZoomScale(zoom, {
          minZoom: 6,
          maxZoom: 12,
          minScale: 0.5,
          maxScale: 0.9,
        });
        (features || []).forEach((feature) => {
          if (!feature || !feature.geometry || !feature.geometry.coordinates) {
            return;
          }
          const props = feature.properties || {};
          const labelText = String(props.label || "").trim();
          if (!labelText) {
            return;
          }
          const markerId =
            typeof props.markerId === "string" && props.markerId
              ? props.markerId
              : `${labelText}:${feature.geometry.coordinates.join(",")}`;
          let angleDeg = 0;
          let offset = [0, 0];
          if (map && props.startCoord && props.endCoord) {
            try {
              const startPx = map.project(props.startCoord);
              const endPx = map.project(props.endCoord);
              const dx = endPx.x - startPx.x;
              const dy = endPx.y - startPx.y;
              if (Number.isFinite(dx) && Number.isFinite(dy) && (dx || dy)) {
                const angle = Math.atan2(dy, dx);
                angleDeg = (angle * 180) / Math.PI;
                if (angleDeg > 90 || angleDeg < -90) {
                  angleDeg += 180;
                }
                const normal = angle + Math.PI / 2;
                const mag = 8 * MAP_SIZE_SCALE * scale;
                offset = [Math.cos(normal) * mag, Math.sin(normal) * mag];
              }
            } catch (_err) {
              // ignore
            }
          }
          let marker = this.corridorScheduleMarkers.get(markerId);
          if (!marker) {
            const label = document.createElement("div");
            label.className = "corridor-schedule-label";
            label.style.transform = `scale(${scale})`;
            const text = document.createElement("div");
            text.className = "corridor-schedule-label-text";
            text.textContent = labelText;
            text.style.transform = angleDeg ? `rotate(${angleDeg}deg)` : "";
            label.appendChild(text);
            marker = new maplibregl.Marker({
              element: label,
              anchor: "center",
              offset,
            })
              .setLngLat(feature.geometry.coordinates)
              .addTo(this.map);
          } else {
            const element = marker.getElement();
            if (element) {
              const textNode =
                element.querySelector && element.querySelector(".corridor-schedule-label-text");
              if (textNode && textNode.textContent !== labelText) {
                textNode.textContent = labelText;
              }
              if (textNode) {
                textNode.style.transform = angleDeg ? `rotate(${angleDeg}deg)` : "";
              }
              element.style.transform = `scale(${scale})`;
            }
            if (marker.setOffset) {
              marker.setOffset(offset);
            }
            marker.setLngLat(feature.geometry.coordinates);
          }
          next.set(markerId, marker);
        });
        this.corridorScheduleMarkers.forEach((marker, key) => {
          if (!next.has(key)) {
            marker.remove();
          }
        });
        this.corridorScheduleMarkers = next;
      },

      checkCorridorTimedChanges(simTime_s) {
        const map = this.corridorTimedActions;
        if (!map || !(map instanceof Map) || map.size === 0) {
          return;
        }
        const now = Number(simTime_s);
        if (!Number.isFinite(now)) {
          return;
        }
        const ready = [];
        map.forEach((entry, timerKey) => {
          if (!entry || !Number.isFinite(entry.untilSim_s)) {
            return;
          }
          if (now >= entry.untilSim_s) {
            ready.push({ entry, timerKey });
          }
        });
        if (!ready.length) {
          return;
        }
        ready.forEach(({ entry, timerKey }) => {
          map.delete(timerKey);
          if (entry.kind === "spare") {
            this.setSpareCorridorOpen(entry.fromName, entry.toName, !entry.openNow, {
              skipTimedClear: true,
            });
          } else {
            this.setCorridorClosure(entry.fromName, entry.toName, entry.openNow, {
              skipTimedClear: true,
            });
          }
        });
        this.updateCorridorTimedLabels(now);
      },

    scheduleCorridorTimedChange({ fromName, toName, kind, openNow, durationMs }) {
      const key = this.getCorridorEdgeKey(fromName, toName);
      if (!key) {
        return;
      }
      const duration = Number(durationMs);
      if (!Number.isFinite(duration) || duration <= 0) {
        if (kind === "spare") {
          this.setSpareCorridorOpen(fromName, toName, Boolean(openNow), { skipTimedClear: true });
        } else {
          this.setCorridorClosure(fromName, toName, !openNow, { skipTimedClear: true });
        }
        return;
      }

      const map = this.ensureCorridorTimedActions();
      const timerKey = `${kind}:${key}`;
      this.clearCorridorTimedChange(kind, key, { silent: true });

      if (kind === "spare") {
        this.setSpareCorridorOpen(fromName, toName, Boolean(openNow), { skipTimedClear: true });
      } else {
        this.setCorridorClosure(fromName, toName, !openNow, { skipTimedClear: true });
      }

      const durationSeconds = duration / 1000;
      const startSim =
        Number.isFinite(this.lastSimTime_s) && this.lastSimTime_s >= 0
          ? this.lastSimTime_s
          : 0;
      const untilSim_s = startSim + durationSeconds;
      map.set(timerKey, {
        kind,
        openNow,
        fromName,
        toName,
        durationSeconds,
        untilSim_s,
      });
      this.updateCorridorTimedLabels(startSim);
      this.addStatusMessage({
        text: `${kind === "spare" ? "Spare link" : "Corridor"} ${openNow ? "opened" : "closed"} for ${Math.round(duration / 60000)} min.`,
        level: "info",
        ttlMs: 3000,
      });
    },

    setCorridorClosure(fromName, toName, closed, options = {}) {
      const key = this.getCorridorEdgeKey(fromName, toName);
      if (!key) {
        return;
      }
      if (!options.skipTimedClear) {
        this.clearCorridorTimedChange("normal", key, { silent: true });
      }
      const wasClosed = this.closedCorridorEdges.has(key);
      if (closed === wasClosed) {
        return;
      }
      if (closed) {
        this.closedCorridorEdges.add(key);
      } else {
        this.closedCorridorEdges.delete(key);
      }
      this.refreshClosedCorridorLines();
      const ok = this.sendControlCommand("setCorridorClosed", fromName, toName, closed);
      if (ok && typeof this.recordHumanIntervention === "function") {
        this.recordHumanIntervention("airspace", {
          action: closed ? "close" : "open",
          from: fromName,
          to: toName,
          kind: "corridor",
        });
      }
      if (!ok) {
        this.addStatusMessage({
          text: "Failed to update corridor status.",
          level: "warn",
          ttlMs: 3000,
        });
      }
    },

    setSpareCorridorOpen(fromName, toName, open, options = {}) {
      const key = this.getCorridorEdgeKey(fromName, toName);
      if (!key) {
        return;
      }
      if (!options.skipTimedClear) {
        this.clearCorridorTimedChange("spare", key, { silent: true });
      }
      const wasOpen =
        this.openSpareCorridorEdges && this.openSpareCorridorEdges.has(key);
      if (open === wasOpen) {
        return;
      }
      if (!this.openSpareCorridorEdges) {
        this.openSpareCorridorEdges = new Set();
      }
      if (open) {
        this.openSpareCorridorEdges.add(key);
      } else {
        this.openSpareCorridorEdges.delete(key);
      }
      if (this.corridorData) {
        this.updateCorridorSpareOpen3dLayer(this.corridorData);
      }
      this.refreshRouteGraph();
      const ok = this.sendControlCommand("setSpareCorridorOpen", fromName, toName, open);
      if (ok && typeof this.recordHumanIntervention === "function") {
        this.recordHumanIntervention("airspace", {
          action: open ? "open" : "close",
          from: fromName,
          to: toName,
          kind: "spare",
        });
      }
      if (!ok) {
        this.addStatusMessage({
          text: "Failed to update spare link status.",
          level: "warn",
          ttlMs: 3000,
        });
      }
      this.addStatusMessage({
        text: open ? "Spare link opened." : "Spare link closed.",
        level: "info",
        ttlMs: 2000,
      });
    },

    toggleSpareCorridorOpen(fromName, toName) {
      const key = this.getCorridorEdgeKey(fromName, toName);
      if (!key) {
        return;
      }
      const wasOpen =
        this.openSpareCorridorEdges && this.openSpareCorridorEdges.has(key);
      this.setSpareCorridorOpen(fromName, toName, !wasOpen);
    },

    toggleCorridorClosure(fromName, toName) {
      const key = this.getCorridorEdgeKey(fromName, toName);
      if (!key) {
        return;
      }
      const wasClosed = this.closedCorridorEdges.has(key);
      this.setCorridorClosure(fromName, toName, !wasClosed);
    },

    refreshClosedCorridorLines() {
      if (!this.corridorLayer || !this.corridorLayer.setClosedLines) {
        return;
      }
      if (!this.corridorData || !this.corridorData.lines) {
        this.corridorLayer.setClosedLines([]);
        return;
      }
      const indices = [];
      this.corridorData.lines.forEach((line, index) => {
        const key = this.getCorridorEdgeKey(line.from, line.to);
        if (key && this.closedCorridorEdges.has(key)) {
          indices.push(index);
        }
      });
      this.corridorClosedLineIndices = indices;
      this.corridorLayer.setClosedLines(indices);
      this.updateCorridorClosed3dLayer();
      if (this.map) {
        this.map.triggerRepaint();
      }
    },

    handleCorridorHover(event) {
      if ((this.isEmergencyLandingMode && this.isEmergencyLandingMode()) ||
          (this.isForceMoveMode && this.isForceMoveMode())) {
        this.clearCorridorHover();
        return;
      }
      if (this.isVertiportEditMode()) {
        if (!this.vertiportLinking) {
          this.clearCorridorHover();
          return;
        }
      }
      if (this.isPlanSelectingPorts()) {
        this.clearCorridorHover();
        return;
      }
      if (this.isTrafficHoverTarget && this.isTrafficHoverTarget(event.point)) {
        this.clearCorridorHover();
        return;
      }
      if (!this.map || !this.corridorLayer || !this.corridorLayer.getMatrix) {
        return;
      }
      const matrix = this.corridorLayer.getMatrix();
      if (!matrix) {
        return;
      }
      if (this.isAirspaceEditMode()) {
        if (this.corridorEditMovingName || this.corridorEditMovingId) {
          this.handleAirspaceEditHover(event);
          return;
        }
        const target = this.findCorridorHoverTarget(event.point, matrix);
        if (target) {
          const isSame =
            this.corridorHover &&
            this.corridorHover.type === target.type &&
            this.corridorHover.index === target.index;
          this.corridorHover = target;
          if (this.corridorLayer.setHover) {
            this.corridorLayer.setHover(target);
          }
          if (this.corridorLinks3dLayer && this.corridorLinks3dLayer.setHoverLine) {
            this.corridorLinks3dLayer.setHoverLine(
              target.type === "line" ? target.index : -1,
            );
          }
          if (this.corridorSpareHoverIndex !== -1) {
            this.setCorridorSpareHoverIndex(-1);
          }
          if (!isSame) {
            this.map.triggerRepaint();
          }
          this.showCorridorLabel(`C : ${target.name}`, event.point);
          this.hideCorridorEditGhost();
          this.hideCorridorEditCoordLabel();
          this.map.getCanvas().style.cursor = "pointer";
          return;
        }
        const spareTarget = this.findCorridorSpareHoverTarget(event.point, matrix);
        if (spareTarget) {
          const isSame =
            this.corridorHover &&
            this.corridorHover.kind === "spare" &&
            this.corridorHover.index === spareTarget.index;
          this.corridorHover = spareTarget;
          this.setCorridorSpareHoverIndex(spareTarget.index);
          if (this.corridorLayer && this.corridorLayer.clearHover) {
            this.corridorLayer.clearHover();
          }
          if (this.corridorLinks3dLayer && this.corridorLinks3dLayer.clearHoverLine) {
            this.corridorLinks3dLayer.clearHoverLine();
          }
          if (!isSame) {
            this.map.triggerRepaint();
          }
          this.showCorridorLabel(`S : ${spareTarget.name}`, event.point);
          this.hideCorridorEditGhost();
          this.hideCorridorEditCoordLabel();
          this.map.getCanvas().style.cursor = "pointer";
          return;
        }
        this.handleAirspaceEditHover(event);
        return;
      }
      const target = this.findCorridorHoverTarget(event.point, matrix);
      if (!target) {
        const spareTarget = this.findCorridorSpareHoverTarget(event.point, matrix);
        if (!spareTarget) {
          this.clearCorridorHover();
          return;
        }
        const isSame =
          this.corridorHover &&
          this.corridorHover.kind === "spare" &&
          this.corridorHover.index === spareTarget.index;
        this.corridorHover = spareTarget;
        this.setCorridorSpareHoverIndex(spareTarget.index);
        if (this.corridorLayer && this.corridorLayer.clearHover) {
          this.corridorLayer.clearHover();
        }
        if (this.corridorLinks3dLayer && this.corridorLinks3dLayer.clearHoverLine) {
          this.corridorLinks3dLayer.clearHoverLine();
        }
        if (!isSame) {
          this.map.triggerRepaint();
        }
        this.showCorridorLabel(`S : ${spareTarget.name}`, event.point);
        this.map.getCanvas().style.cursor = "pointer";
        return;
      }
      if (this.corridorSpareHoverIndex !== -1) {
        this.setCorridorSpareHoverIndex(-1);
      }

      const isSame =
        this.corridorHover &&
        this.corridorHover.type === target.type &&
        this.corridorHover.index === target.index;
      this.corridorHover = target;
      if (this.corridorLayer.setHover) {
        this.corridorLayer.setHover(target);
      }
      if (this.corridorLinks3dLayer && this.corridorLinks3dLayer.setHoverLine) {
        this.corridorLinks3dLayer.setHoverLine(target.type === "line" ? target.index : -1);
      }
      if (!isSame) {
        this.map.triggerRepaint();
      }
      this.showCorridorLabel(`C : ${target.name}`, event.point);
      this.map.getCanvas().style.cursor = "pointer";
    },

    showCorridorLabel(text, point) {
      if (!this.corridorHoverLabel) {
        return;
      }
      this.corridorHoverLabel.textContent = text;
      this.corridorHoverLabel.style.left = `${point.x}px`;
      this.corridorHoverLabel.style.top = `${point.y}px`;
      this.corridorHoverLabel.classList.add("is-visible");
    },

    clearCorridorHover() {
      if (!this.map) {
        return;
      }
      const hadHover = Boolean(this.corridorHover);
      this.corridorHover = null;
      if (this.corridorLayer && this.corridorLayer.clearHover) {
        this.corridorLayer.clearHover();
      }
      if (this.corridorLinks3dLayer && this.corridorLinks3dLayer.clearHoverLine) {
        this.corridorLinks3dLayer.clearHoverLine();
      }
      this.setCorridorSpareHoverIndex(-1);
      if (hadHover) {
        this.map.triggerRepaint();
      }
      if (this.corridorHoverLabel) {
        this.corridorHoverLabel.classList.remove("is-visible");
      }
      if ((this.isEmergencyLandingMode && this.isEmergencyLandingMode()) ||
          (this.isForceMoveMode && this.isForceMoveMode())) {
        this.map.getCanvas().style.cursor = "crosshair";
      } else if (!this.vertiportHover) {
        this.map.getCanvas().style.cursor = "";
      }
    },

    setCorridorSpareHoverIndex(nextIndex) {
      const index = Number.isFinite(nextIndex) ? nextIndex : -1;
      if (index === this.corridorSpareHoverIndex) {
        return;
      }
      this.corridorSpareHoverIndex = index;
      if (this.corridorSpareLinks3dLayer && this.corridorSpareLinks3dLayer.setHoverLine) {
        let mapped = index;
        if (this.corridorSpareLinkDashIndex && index > -1) {
          const dashIndex = this.corridorSpareLinkDashIndex[index];
          if (dashIndex != null) {
            mapped = dashIndex;
          }
        }
        this.corridorSpareLinks3dLayer.setHoverLine(mapped);
      }
      if (this.map) {
        this.map.triggerRepaint();
      }
    },

    normalizeLngLat(lngLat) {
      if (!lngLat) {
        return null;
      }
      const lng = Number(lngLat.lng);
      const lat = Number(lngLat.lat);
      if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
        return null;
      }
      return { lng, lat };
    },

    ensureCorridorEditGhost() {
      if (!this.map) {
        return;
      }
      this.ensureCorridorEditLayer();
    },

    showCorridorEditGhost(lngLat) {
      if (!this.map || !lngLat) {
        return;
      }
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return;
      }
      this.corridorEditGhostLngLat = normalized;
      this.ensureCorridorEditLayer();
      this.updateCorridorEditSource();
    },

    hideCorridorEditGhost() {
      if (this.corridorEditGhostLngLat) {
        this.corridorEditGhostLngLat = null;
        this.updateCorridorEditSource();
      }
    },

    updateCorridorEditCoordLabel(point, lngLat) {
      if (!this.corridorEditCoordLabel || !point || !lngLat) {
        return;
      }
      const lat = Number(lngLat.lat);
      const lon = Number(lngLat.lng);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        return;
      }
      this.corridorEditCoordLabel.textContent = this.t("label.lat_lon", {
        lat: lat.toFixed(6),
        lon: lon.toFixed(6),
      });
      this.corridorEditCoordLabel.style.left = `${point.x}px`;
      this.corridorEditCoordLabel.style.top = `${point.y}px`;
      this.corridorEditCoordLabel.classList.add("is-visible");
    },

    hideCorridorEditCoordLabel() {
      if (this.corridorEditCoordLabel) {
        this.corridorEditCoordLabel.classList.remove("is-visible");
      }
    },

    handleAirspaceEditHover(event) {
      if (!this.map || !this.isAirspaceEditMode()) {
        this.hideCorridorEditGhost();
        this.hideCorridorEditCoordLabel();
        return false;
      }
      const { point, lngLat } = this.resolveMapPointer(event);
      if (this.corridorEditMovingName) {
        if (lngLat) {
          this.showCorridorEditGhost(lngLat);
        } else {
          this.hideCorridorEditGhost();
        }
        this.clearCorridorHover();
        if (point && lngLat) {
          this.updateCorridorEditCoordLabel(point, lngLat);
        }
        this.map.getCanvas().style.cursor = "crosshair";
        return true;
      }
      if (this.corridorEditMovingId) {
        const node = this.corridorPendingNodes.get(this.corridorEditMovingId);
        if (node && lngLat) {
          this.updatePendingCorridorNodePosition(node, lngLat);
        }
        this.hideCorridorEditGhost();
        this.clearCorridorHover();
        if (point && lngLat) {
          this.updateCorridorEditCoordLabel(point, lngLat);
        }
        this.map.getCanvas().style.cursor = "crosshair";
        return true;
      }
      if (this.corridorLinking) {
        this.hideCorridorEditGhost();
        this.hideCorridorEditCoordLabel();
        this.clearCorridorHover();
        this.map.getCanvas().style.cursor = "crosshair";
        return true;
      }
      if (this.isAirspaceNodeToolActive()) {
        if (lngLat) {
          this.showCorridorEditGhost(lngLat);
        }
        this.clearCorridorHover();
        if (point && lngLat) {
          this.updateCorridorEditCoordLabel(point, lngLat);
        }
        this.map.getCanvas().style.cursor = "crosshair";
        return true;
      }
      this.hideCorridorEditGhost();
      this.hideCorridorEditCoordLabel();
      return false;
    },

    handleAirspaceEditClick(event) {
      if (!this.map || !this.isAirspaceEditMode()) {
        return false;
      }
      const { point, lngLat } = this.resolveMapPointer(event);
      if (
        point &&
        this.shouldTriggerRepeatTapContext &&
        this.shouldTriggerRepeatTapContext("airspace-edit", point)
      ) {
        const synthetic = this.buildSyntheticContextMenuEvent
          ? this.buildSyntheticContextMenuEvent(point, lngLat)
          : { point, lngLat, originalEvent: { preventDefault() {}, stopPropagation() {} } };
        this.handleAirspaceEditContextMenu(synthetic);
        return true;
      }
      if (this.corridorEditMovingName) {
        const targetName = this.corridorEditMovingName;
        if (lngLat) {
          void this.updateExistingCorridorPosition(targetName, lngLat);
          this.corridorEditMovingName = null;
          this.clearCorridorEditHighlight();
          this.hideCorridorEditGhost();
          this.hideCorridorEditCoordLabel();
        }
        return true;
      }
      if (this.corridorEditMovingId) {
        const node = this.corridorPendingNodes.get(this.corridorEditMovingId);
        if (node && lngLat) {
          this.updatePendingCorridorNodePosition(node, lngLat);
        }
        this.corridorEditMovingId = null;
        return true;
      }
      if (this.corridorLinking) {
        if (point) {
          const pendingId = this.pickPendingCorridorAt(point);
          if (pendingId) {
            this.addStatusMessage({
              text: "Confirm the node before linking.",
              level: "info",
              ttlMs: 2500,
            });
            return true;
          }
          const pickedName = this.pickCorridorAt(point);
          if (pickedName) {
            return this.handleCorridorLinkSelection(pickedName, lngLat);
          }
        }
        return true;
      }
      if (!this.isAirspaceNodeToolActive()) {
        return true;
      }
      if (point) {
        const pendingId = this.pickPendingCorridorAt(point);
        if (pendingId) {
          this.toggleCorridorPendingPopup(pendingId);
          return true;
        }
      }
      if (this.isTrafficHoverTarget && point && this.isTrafficHoverTarget(point)) {
        return true;
      }
      if (point) {
        const pickedName = this.pickCorridorAt(point);
        if (pickedName) {
          this.toggleCorridorExistingPopup(pickedName, lngLat);
          return true;
        }
      }
      if (lngLat) {
        this.createPendingCorridorNode(lngLat);
      }
      return true;
    },

    handleAirspaceEditContextMenu(event) {
      if ((this.isEmergencyLandingMode && this.isEmergencyLandingMode()) ||
          (this.isForceMoveMode && this.isForceMoveMode())) {
        if (event && event.originalEvent) {
          if (event.originalEvent.preventDefault) {
            event.originalEvent.preventDefault();
          }
          if (event.originalEvent.stopPropagation) {
            event.originalEvent.stopPropagation();
          }
        }
        return true;
      }
      if (!this.map || !this.isAirspaceEditMode()) {
        return false;
      }
      if (this.scaleCopyActive) {
        return false;
      }
      if (this.corridorLinking) {
        if (event && event.originalEvent) {
          if (event.originalEvent.preventDefault) {
            event.originalEvent.preventDefault();
          }
          if (event.originalEvent.stopPropagation) {
            event.originalEvent.stopPropagation();
          }
        }
        this.clearCorridorLinking();
        return true;
      }
      const { point } = this.resolveMapPointer(event);
      if (!point) {
        return false;
      }
      const matrix =
        this.corridorLayer && this.corridorLayer.getMatrix ? this.corridorLayer.getMatrix() : null;
      if (matrix) {
        const target = this.findCorridorHoverTarget(point, matrix);
        if (target && target.type === "line") {
          const line =
            this.corridorHitData && this.corridorHitData.lines
              ? this.corridorHitData.lines[target.index]
              : null;
          if (line && line.start && line.end) {
            if (event && event.originalEvent) {
              if (event.originalEvent.preventDefault) {
                event.originalEvent.preventDefault();
              }
              if (event.originalEvent.stopPropagation) {
                event.originalEvent.stopPropagation();
              }
            }
            void this.removeCorridorLink(line.start.name, line.end.name, "normal");
            return true;
          }
        }
        const spareTarget = this.findCorridorSpareHoverTarget(point, matrix);
        if (spareTarget && spareTarget.type === "line") {
          const line =
            this.corridorSpareHitData && this.corridorSpareHitData.lines
              ? this.corridorSpareHitData.lines[spareTarget.index]
              : null;
          if (line && line.start && line.end) {
            if (event && event.originalEvent) {
              if (event.originalEvent.preventDefault) {
                event.originalEvent.preventDefault();
              }
              if (event.originalEvent.stopPropagation) {
                event.originalEvent.stopPropagation();
              }
            }
            void this.removeCorridorLink(line.start.name, line.end.name, "spare");
            return true;
          }
        }
      }
      if (!this.isAirspaceNodeToolActive()) {
        return false;
      }
      const pendingId = this.pickPendingCorridorAt(point);
      if (!pendingId) {
        return false;
      }
      if (event && event.originalEvent) {
        if (event.originalEvent.preventDefault) {
          event.originalEvent.preventDefault();
        }
        if (event.originalEvent.stopPropagation) {
          event.originalEvent.stopPropagation();
        }
      }
      this.removePendingCorridorNode(pendingId);
      return true;
    },

    ensureCorridorEditLayer() {
      if (!this.map) {
        return;
      }
      const sourceId = "corridor-edit";
      if (!this.map.getSource(sourceId)) {
        this.map.addSource(sourceId, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!this.map.getLayer("corridor-edit-ring")) {
        this.map.addLayer({
          id: "corridor-edit-ring",
          type: "circle",
          source: sourceId,
          filter: ["==", ["get", "kind"], "highlight"],
          paint: {
            "circle-radius": 12 * MAP_SIZE_SCALE,
            "circle-color": "#000000",
            "circle-opacity": 0,
            "circle-stroke-color": HOVER_OUTLINE_COLOR,
            "circle-stroke-opacity": 0.95,
            "circle-stroke-width": 3.5 * MAP_SIZE_SCALE,
          },
        });
      }
      if (!this.map.getLayer("corridor-edit-circle")) {
        const corridorColor = this.getCorridorColor(this.currentTheme);
        this.map.addLayer({
          id: "corridor-edit-circle",
          type: "circle",
          source: sourceId,
          filter: ["!=", ["get", "kind"], "highlight"],
          paint: {
            "circle-radius": [
              "case",
              ["==", ["get", "kind"], "ghost"],
              3.5 * MAP_SIZE_SCALE,
              4 * MAP_SIZE_SCALE,
            ],
            "circle-color": [
              "case",
              ["==", ["get", "kind"], "ghost"],
              "#8fb5ff",
              corridorColor,
            ],
            "circle-opacity": [
              "case",
              ["==", ["get", "kind"], "ghost"],
              0.6,
              1,
            ],
            "circle-stroke-color": [
              "case",
              ["==", ["get", "kind"], "ghost"],
              "#6c8cd6",
              "#10254f",
            ],
            "circle-stroke-width": [
              "case",
              ["==", ["get", "kind"], "ghost"],
              1.1 * MAP_SIZE_SCALE,
              1.4 * MAP_SIZE_SCALE,
            ],
          },
        });
      }
      this.reorderPlanLayers();
      this.updateCorridorEditSource();
    },

    updateCorridorEditSource() {
      if (!this.map) {
        return;
      }
      const source = this.map.getSource("corridor-edit");
      if (!source || !source.setData) {
        return;
      }
      const features = [];
      if (this.corridorEditGhostLngLat) {
        features.push({
          type: "Feature",
          id: "ghost",
          geometry: {
            type: "Point",
            coordinates: [this.corridorEditGhostLngLat.lng, this.corridorEditGhostLngLat.lat],
          },
          properties: { kind: "ghost" },
        });
      }
      this.corridorPendingNodes.forEach((node) => {
        if (!node || !node.lngLat) {
          return;
        }
        features.push({
          type: "Feature",
          id: node.id,
          geometry: {
            type: "Point",
            coordinates: [node.lngLat.lng, node.lngLat.lat],
          },
          properties: { kind: "pending", nodeId: node.id },
        });
      });
      source.setData({ type: "FeatureCollection", features });
    },

    pickPendingCorridorAt(point) {
      if (!this.map) {
        return null;
      }
      if (!this.map.getLayer("corridor-edit-circle")) {
        return null;
      }
      const features = this.map.queryRenderedFeatures(point, {
        layers: ["corridor-edit-circle"],
      });
      if (!features.length) {
        return null;
      }
      const target = features.find(
        (feature) => feature.properties && feature.properties.kind === "pending",
      );
      if (!target) {
        return null;
      }
      const props = target.properties || {};
      const id = props.nodeId || target.id;
      return id ? String(id) : null;
    },

    createPendingCorridorNode(lngLat) {
      if (!this.map || !lngLat) {
        return null;
      }
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return null;
      }
      const id = `pending-${(this.corridorPendingCounter += 1)}`;
      const node = { id, lngLat: normalized };
      this.corridorPendingNodes.set(id, node);
      this.ensureCorridorEditLayer();
      this.updateCorridorEditSource();
      return node;
    },

    updatePendingCorridorNodePosition(node, lngLat) {
      if (!node || !lngLat) {
        return;
      }
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return;
      }
      node.lngLat = normalized;
      this.updateCorridorEditSource();
    },

    removePendingCorridorNode(nodeId) {
      const node = this.corridorPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      this.corridorPendingNodes.delete(nodeId);
      this.updateCorridorEditSource();
      if (this.corridorEditPopupNodeId === nodeId) {
        this.hideCorridorEditPopup();
      }
      if (this.corridorEditMovingId === nodeId) {
        this.corridorEditMovingId = null;
      }
    },

    ensureCorridorEditPopup() {
      if (this.corridorEditPopup) {
        return this.corridorEditPopup;
      }
      const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: true,
        className: "vertiport-edit-popup",
      });
      if (popup.on) {
        popup.on("close", () => {
          this.corridorEditPopupNodeId = null;
          this.corridorEditPopupName = null;
          if (!this.corridorEditMovingName) {
            this.clearCorridorEditHighlight();
          }
        });
      }
      this.corridorEditPopup = popup;
      return popup;
    },

    hideCorridorEditPopup() {
      if (this.corridorEditPopup) {
        this.corridorEditPopup.remove();
      }
      this.corridorEditPopupNodeId = null;
      this.corridorEditPopupName = null;
    },

    ensureCorridorLinkPopup() {
      if (this.corridorLinkPopup) {
        return this.corridorLinkPopup;
      }
      const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: true,
        className: "vertiport-edit-popup",
      });
      if (popup.on) {
        popup.on("close", () => {
          this.corridorLinking = null;
          this.clearCorridorLinkPreview();
          if (!this.corridorEditMovingName) {
            this.clearCorridorEditHighlight();
          }
        });
      }
      this.corridorLinkPopup = popup;
      return popup;
    },

    hideCorridorLinkPopup() {
      if (this.corridorLinkPopup) {
        this.corridorLinkPopup.remove();
      }
    },

    toggleCorridorPendingPopup(nodeId) {
      if (!this.map) {
        return;
      }
      const node = this.corridorPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      if (this.corridorEditPopupNodeId === nodeId) {
        this.hideCorridorEditPopup();
        return;
      }
      const popup = this.ensureCorridorEditPopup();
      popup
        .setLngLat(node.lngLat)
        .setDOMContent(this.buildCorridorPendingPopupContent(nodeId))
        .addTo(this.map);
      this.corridorEditPopupNodeId = nodeId;
      this.corridorEditPopupName = null;
    },

    buildCorridorPendingPopupContent(nodeId) {
      const card = document.createElement("div");
      card.className = "vertiport-edit-card";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Corridor Node";
      card.appendChild(title);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions vertiport-edit-actions-wide";

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Move", () => {
          this.corridorEditMovingId = nodeId;
          this.hideCorridorEditPopup();
        }),
      );
      actions.appendChild(
        buildButton("Delete", () => {
          this.removePendingCorridorNode(nodeId);
        }),
      );
      actions.appendChild(
        buildButton("Confirm", () => {
          this.showCorridorConfirmPopup(nodeId);
        }),
      );
      card.appendChild(actions);
      return card;
    },

    pickCorridorAt(point) {
      if (!this.map || !this.corridorLayer || !this.corridorLayer.getMatrix) {
        return null;
      }
      const matrix = this.corridorLayer.getMatrix();
      if (!matrix) {
        return null;
      }
      const target = this.findCorridorHoverTarget(point, matrix);
      if (!target || target.type !== "point") {
        return null;
      }
      return target.name ? String(target.name) : null;
    },

    toggleCorridorExistingPopup(name, lngLat) {
      if (!this.map) {
        return;
      }
      const entry = this.corridorPointLookup ? this.corridorPointLookup.get(name) : null;
      if (!entry) {
        return;
      }
      if (this.corridorEditPopupName === name) {
        this.hideCorridorEditPopup();
        this.clearCorridorEditHighlight();
        return;
      }
      const anchorLngLat =
        lngLat && Number.isFinite(lngLat.lng) && Number.isFinite(lngLat.lat)
          ? lngLat
          : { lng: entry.coord[0], lat: entry.coord[1] };
      const popup = this.ensureCorridorEditPopup();
      popup
        .setLngLat(anchorLngLat)
        .setDOMContent(this.buildCorridorExistingPopupContent(name))
        .addTo(this.map);
      this.corridorEditPopupNodeId = null;
      this.corridorEditPopupName = name;
      this.setCorridorEditHighlight(name);
    },

    buildCorridorExistingPopupContent(name) {
      const entry = this.corridorPointLookup ? this.corridorPointLookup.get(name) : null;
      const card = document.createElement("div");
      card.className = "vertiport-edit-card";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      const titleText =
        entry && entry.name
          ? this.t("label.corridor_named", { name: entry.name })
          : this.translateLiteral("Corridor");
      title.textContent = titleText;
      card.appendChild(title);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions vertiport-edit-actions-wide";

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Move", () => {
          if (!entry || !entry.coord) {
            return;
          }
          this.corridorEditMovingName = name;
          this.setCorridorEditHighlight(name);
          this.corridorEditGhostLngLat = { lng: entry.coord[0], lat: entry.coord[1] };
          this.ensureCorridorEditLayer();
          this.updateCorridorEditSource();
          this.hideCorridorEditPopup();
          this.addStatusMessage({
            text: "Click map to set new corridor position.",
            level: "info",
            ttlMs: 3500,
          });
        }),
      );
      actions.appendChild(
        buildButton("Link", () => {
          this.startCorridorLinking(name);
        }),
      );
      actions.appendChild(
        buildButton("Edit", () => {
          this.showCorridorExistingEditPopup(name);
        }),
      );
      actions.appendChild(
        buildButton("Delete", () => {
          this.showCorridorExistingDeletePopup(name);
        }),
      );
      card.appendChild(actions);
      return card;
    },

    startCorridorLinking(name) {
      if (!name) {
        return;
      }
      this.clearCorridorLinking();
      if (this.ensureEditableFile) {
        void this.ensureEditableFile("corridor");
      }
      const entry = this.corridorPointLookup ? this.corridorPointLookup.get(name) : null;
      if (!entry) {
        return;
      }
      this.corridorLinking = { from: name, stage: "pick" };
      this.setCorridorEditHighlight(name);
      this.hideCorridorEditPopup();
      this.clearCorridorLinkPreview();
      this.addStatusMessage({
        text: this.t("status.select_corridor_target", { name }),
        level: "info",
        ttlMs: 3000,
      });
    },

    clearCorridorLinking() {
      if (!this.corridorLinking) {
        this.hideCorridorLinkPopup();
        this.clearCorridorLinkPreview();
        if (!this.corridorEditMovingName) {
          this.clearCorridorEditHighlight();
        }
        return;
      }
      this.corridorLinking = null;
      this.hideCorridorLinkPopup();
      this.clearCorridorLinkPreview();
      if (!this.corridorEditMovingName) {
        this.clearCorridorEditHighlight();
      }
    },

    handleCorridorLinkSelection(targetName, lngLat) {
      if (!this.corridorLinking || !this.corridorLinking.from) {
        return false;
      }
      if (!targetName) {
        return false;
      }
      if (this.corridorLinking.stage === "type") {
        return true;
      }
      if (targetName === this.corridorLinking.from) {
        this.addStatusMessage({
          text: "Select a different corridor node.",
          level: "warn",
          ttlMs: 2500,
        });
        return true;
      }
      this.corridorLinking = {
        from: this.corridorLinking.from,
        to: targetName,
        stage: "type",
      };
      this.setCorridorLinkPreview(this.corridorLinking.from, targetName);
      this.showCorridorLinkTypePopup(this.corridorLinking.from, targetName, lngLat);
      return true;
    },

    showCorridorLinkTypePopup(fromName, toName, lngLat) {
      if (!this.map) {
        return;
      }
      const popup = this.ensureCorridorLinkPopup();
      const card = document.createElement("div");
      card.className = "vertiport-edit-card vertiport-edit-confirm";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Create corridor link";
      card.appendChild(title);
      const body = document.createElement("div");
      body.className = "vertiport-edit-confirm-body";
      body.textContent = `${fromName} -> ${toName}`;
      card.appendChild(body);

      const options = document.createElement("div");
      options.className = "vertiport-edit-options";
      const buildOption = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-option";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };
      options.appendChild(
        buildOption("Normal link", () => {
          void this.commitCorridorLink(fromName, toName, "normal");
        }),
      );
      options.appendChild(
        buildOption("Spare link", () => {
          void this.commitCorridorLink(fromName, toName, "spare");
        }),
      );
      card.appendChild(options);

      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "vertiport-edit-btn";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", (event) => {
        event.stopPropagation();
        this.clearCorridorLinking();
      });
      actions.appendChild(cancel);
      card.appendChild(actions);

      const entry = this.corridorPointLookup ? this.corridorPointLookup.get(toName) : null;
      const anchor =
        lngLat && Number.isFinite(lngLat.lng) && Number.isFinite(lngLat.lat)
          ? lngLat
          : entry
            ? { lng: entry.coord[0], lat: entry.coord[1] }
            : null;
      if (anchor) {
        popup.setLngLat(anchor).setDOMContent(card).addTo(this.map);
      }
    },

    getCorridorLinkList(name, isSpare) {
      const lookup = isSpare ? this.corridorSpareLinkLookup : this.corridorLinkLookup;
      const list = lookup && lookup.get(name) ? lookup.get(name) : [];
      const seen = new Set();
      const cleaned = [];
      list.forEach((entry) => {
        const value = String(entry || "").trim();
        if (!value || seen.has(value)) {
          return;
        }
        seen.add(value);
        cleaned.push(value);
      });
      return cleaned;
    },

    async commitCorridorLink(fromName, toName, linkType) {
      if (
        !this.corridorPointLookup ||
        !this.corridorPointLookup.has(fromName) ||
        !this.corridorPointLookup.has(toName)
      ) {
        this.addStatusMessage({
          text: "Corridor node not found.",
          level: "warn",
          ttlMs: 2500,
        });
        this.clearCorridorLinking();
        return;
      }
      const kind = linkType === "spare" ? "spare" : "normal";
      const fromLinks = this.getCorridorLinkList(fromName, false);
      const toLinks = this.getCorridorLinkList(toName, false);
      const fromSpare = this.getCorridorLinkList(fromName, true);
      const toSpare = this.getCorridorLinkList(toName, true);
      const formatList = (list) => list.filter(Boolean).join(", ");
      const original = {
        fromLink: formatList(fromLinks),
        toLink: formatList(toLinks),
        fromSpare: formatList(fromSpare),
        toSpare: formatList(toSpare),
      };

      const addUnique = (list, value) => {
        if (!list.includes(value)) {
          list.push(value);
        }
      };
      const removeValue = (list, value) => list.filter((entry) => entry !== value);

      if (kind === "normal") {
        addUnique(fromLinks, toName);
        addUnique(toLinks, fromName);
        fromSpare.splice(0, fromSpare.length, ...removeValue(fromSpare, toName));
        toSpare.splice(0, toSpare.length, ...removeValue(toSpare, fromName));
      } else {
        addUnique(fromSpare, toName);
        addUnique(toSpare, fromName);
        fromLinks.splice(0, fromLinks.length, ...removeValue(fromLinks, toName));
        toLinks.splice(0, toLinks.length, ...removeValue(toLinks, fromName));
      }

      const next = {
        fromLink: formatList(fromLinks),
        toLink: formatList(toLinks),
        fromSpare: formatList(fromSpare),
        toSpare: formatList(toSpare),
      };
      const updates = [];
      if (next.fromLink !== original.fromLink || next.fromSpare !== original.fromSpare) {
        updates.push({
          name: fromName,
          updates: {
            link: next.fromLink,
            spare_link: next.fromSpare,
          },
        });
      }
      if (next.toLink !== original.toLink || next.toSpare !== original.toSpare) {
        updates.push({
          name: toName,
          updates: {
            link: next.toLink,
            spare_link: next.toSpare,
          },
        });
      }

      if (!updates.length) {
        this.addStatusMessage({
          text: "Link already exists.",
          level: "info",
          ttlMs: 2500,
        });
        this.clearCorridorLinking();
        return;
      }

      const ok = await this.applyCorridorBatchUpdate(updates, "Corridor link updated.");
      if (ok) {
        this.clearCorridorLinking();
      }
    },

    async removeCorridorLink(fromName, toName, linkType) {
      if (
        !this.corridorPointLookup ||
        !this.corridorPointLookup.has(fromName) ||
        !this.corridorPointLookup.has(toName)
      ) {
        this.addStatusMessage({
          text: "Corridor node not found.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const isSpare = linkType === "spare";
      const formatList = (list) => list.filter(Boolean).join(", ");
      const removeValue = (list, value) => list.filter((entry) => entry !== value);

      let fromLinks = this.getCorridorLinkList(fromName, false);
      let toLinks = this.getCorridorLinkList(toName, false);
      let fromSpare = this.getCorridorLinkList(fromName, true);
      let toSpare = this.getCorridorLinkList(toName, true);

      const original = {
        fromLink: formatList(fromLinks),
        toLink: formatList(toLinks),
        fromSpare: formatList(fromSpare),
        toSpare: formatList(toSpare),
      };

      if (isSpare) {
        fromSpare = removeValue(fromSpare, toName);
        toSpare = removeValue(toSpare, fromName);
      } else {
        fromLinks = removeValue(fromLinks, toName);
        toLinks = removeValue(toLinks, fromName);
      }

      const next = {
        fromLink: formatList(fromLinks),
        toLink: formatList(toLinks),
        fromSpare: formatList(fromSpare),
        toSpare: formatList(toSpare),
      };
      const updates = [];
      if (next.fromLink !== original.fromLink || next.fromSpare !== original.fromSpare) {
        updates.push({
          name: fromName,
          updates: {
            link: next.fromLink,
            spare_link: next.fromSpare,
          },
        });
      }
      if (next.toLink !== original.toLink || next.toSpare !== original.toSpare) {
        updates.push({
          name: toName,
          updates: {
            link: next.toLink,
            spare_link: next.toSpare,
          },
        });
      }

      if (!updates.length) {
        this.addStatusMessage({
          text: "Link already removed.",
          level: "info",
          ttlMs: 2500,
        });
        return;
      }

      await this.applyCorridorBatchUpdate(updates, "Corridor link removed.");
    },

    showCorridorExistingEditPopup(name) {
      if (!this.map) {
        return;
      }
      const entry = this.corridorPointLookup ? this.corridorPointLookup.get(name) : null;
      if (!entry) {
        return;
      }
      const popup = this.ensureCorridorEditPopup();
      const card = document.createElement("div");
      card.className = "vertiport-edit-card vertiport-edit-confirm";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Edit corridor node";
      card.appendChild(title);
      const body = document.createElement("div");
      body.className = "vertiport-edit-confirm-body";
      card.appendChild(body);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions";
      card.appendChild(actions);

      const input = document.createElement("input");
      input.type = "text";
      input.className = "vertiport-edit-input";
      input.value = entry.name || name;
      input.placeholder = "Name";
      body.appendChild(input);

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Cancel", () => {
          this.hideCorridorEditPopup();
        }),
      );
      actions.appendChild(
        buildButton("Save", () => {
          const value = input.value.trim();
          if (!value) {
            this.addStatusMessage({
              text: "Enter a name first.",
              level: "warn",
              ttlMs: 2500,
            });
            return;
          }
          if (
            value !== name &&
            this.corridorPointLookup &&
            this.corridorPointLookup.has(value)
          ) {
            this.addStatusMessage({
              text: "Corridor name already exists.",
              level: "warn",
              ttlMs: 3000,
            });
            return;
          }
          void this.updateExistingCorridor(name, { name: value });
        }),
      );

      popup
        .setLngLat({ lng: entry.coord[0], lat: entry.coord[1] })
        .setDOMContent(card)
        .addTo(this.map);
      this.corridorEditPopupNodeId = null;
      this.corridorEditPopupName = name;
      input.focus();
    },

    showCorridorExistingDeletePopup(name) {
      if (!this.map) {
        return;
      }
      const entry = this.corridorPointLookup ? this.corridorPointLookup.get(name) : null;
      if (!entry) {
        return;
      }
      const popup = this.ensureCorridorEditPopup();
      const card = document.createElement("div");
      card.className = "vertiport-edit-card vertiport-edit-confirm";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Delete corridor node";
      card.appendChild(title);
      const body = document.createElement("div");
      body.className = "vertiport-edit-confirm-body";
      body.textContent = entry.name
        ? this.t("label.delete_corridor_named", { name: entry.name })
        : this.t("label.delete_corridor");
      card.appendChild(body);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions";
      card.appendChild(actions);

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Cancel", () => {
          this.hideCorridorEditPopup();
        }),
      );
      actions.appendChild(
        buildButton("Delete", () => {
          void this.deleteExistingCorridor(name);
        }),
      );

      popup
        .setLngLat({ lng: entry.coord[0], lat: entry.coord[1] })
        .setDOMContent(card)
        .addTo(this.map);
      this.corridorEditPopupNodeId = null;
      this.corridorEditPopupName = name;
    },

    async applyCorridorUpdate(targetName, updates, successText) {
      const name = String(targetName || "").trim();
      if (!name) {
        return false;
      }
      const ready = await this.ensureEditableFile("corridor");
      if (!ready) {
        return false;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.corridor &&
        this.fileControls.corridor.nameInput
          ? this.fileControls.corridor.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active corridor file.",
          level: "warn",
          ttlMs: 2500,
        });
        return false;
      }
      const payload = {
        kind: "corridor",
        file: fileName,
        target: name,
        updates: updates || {},
      };
      const result = await this.requestDatafileUpdate(payload);
      if (!result || !result.ok) {
        const message =
          result && typeof result.message === "string" && result.message
            ? result.message
            : "Failed to update corridor.";
        this.addStatusMessage({
          text: message,
          level: "warn",
          ttlMs: 3000,
        });
        return false;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("corridor", nextName, { custom: true });
      this.config.data.waypointCsv = nextUrl;
      await this.loadCorridorTable(nextUrl);
      await this.loadCorridorOverlay();
      if (this.applyDatafilesToServer) {
        await this.applyDatafilesToServer();
      }
      if (successText) {
        this.addStatusMessage({
          text: successText,
          level: "success",
          ttlMs: 3000,
        });
      }
      return true;
    },

    async applyCorridorBatchUpdate(entries, successText) {
      const updates = Array.isArray(entries) ? entries : [];
      if (!updates.length) {
        return false;
      }
      const ready = await this.ensureEditableFile("corridor");
      if (!ready) {
        return false;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.corridor &&
        this.fileControls.corridor.nameInput
          ? this.fileControls.corridor.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active corridor file.",
          level: "warn",
          ttlMs: 2500,
        });
        return false;
      }
      let lastResult = null;
      let applied = false;
      for (const item of updates) {
        if (!item || !item.name || !item.updates || !Object.keys(item.updates).length) {
          continue;
        }
        const payload = {
          kind: "corridor",
          file: fileName,
          target: String(item.name),
          updates: item.updates,
        };
        const result = await this.requestDatafileUpdate(payload);
        if (!result || !result.ok) {
          const message =
            result && typeof result.message === "string" && result.message
              ? result.message
              : "Failed to update corridor.";
          this.addStatusMessage({
            text: message,
            level: "warn",
            ttlMs: 3000,
          });
          break;
        }
        lastResult = result;
        applied = true;
      }
      if (!applied) {
        return false;
      }
      const nextName = lastResult && typeof lastResult.name === "string" ? lastResult.name : fileName;
      const nextUrl =
        lastResult && typeof lastResult.url === "string" && lastResult.url
          ? lastResult.url
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("corridor", nextName, { custom: true });
      this.config.data.waypointCsv = nextUrl;
      await this.loadCorridorTable(nextUrl);
      await this.loadCorridorOverlay();
      if (this.applyDatafilesToServer) {
        await this.applyDatafilesToServer();
      }
      if (successText) {
        this.addStatusMessage({
          text: successText,
          level: "success",
          ttlMs: 3000,
        });
      }
      return true;
    },

    async updateExistingCorridorPosition(name, lngLat) {
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return;
      }
      const ok = await this.applyCorridorUpdate(
        name,
        { lat: normalized.lat, lon: normalized.lng },
        "Corridor position updated.",
      );
      if (ok) {
        this.hideCorridorEditPopup();
      }
    },

    async updateExistingCorridor(name, updates) {
      const payload = updates && typeof updates === "object" ? updates : {};
      const nextName =
        Object.prototype.hasOwnProperty.call(payload, "name") &&
        typeof payload.name === "string"
          ? payload.name.trim()
          : String(name || "").trim();
      if (!nextName) {
        this.addStatusMessage({
          text: "Enter a name first.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      if (
        nextName !== name &&
        this.corridorPointLookup &&
        this.corridorPointLookup.has(nextName)
      ) {
        this.addStatusMessage({
          text: "Corridor name already exists.",
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const updatesPayload = {};
      if (Object.prototype.hasOwnProperty.call(payload, "name")) {
        updatesPayload.name = nextName;
      }
      if (Object.prototype.hasOwnProperty.call(payload, "lat")) {
        updatesPayload.lat = payload.lat;
      }
      if (Object.prototype.hasOwnProperty.call(payload, "lon")) {
        updatesPayload.lon = payload.lon;
      }
      const ok = await this.applyCorridorUpdate(name, updatesPayload, "Corridor updated.");
      if (ok) {
        this.hideCorridorEditPopup();
      }
    },

    async deleteExistingCorridor(name) {
      const target = String(name || "").trim();
      if (!target) {
        return;
      }
      const ready = await this.ensureEditableFile("corridor");
      if (!ready) {
        return;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.corridor &&
        this.fileControls.corridor.nameInput
          ? this.fileControls.corridor.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active corridor file.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const payload = {
        kind: "corridor",
        file: fileName,
        target,
      };
      const result = await this.requestDatafileDelete(payload);
      if (!result || !result.ok) {
        const message =
          result && typeof result.message === "string" && result.message
            ? result.message
            : "Failed to delete corridor.";
        this.addStatusMessage({
          text: message,
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("corridor", nextName, { custom: true });
      this.config.data.waypointCsv = nextUrl;
      await this.loadCorridorTable(nextUrl);
      await this.loadCorridorOverlay();
      if (this.applyDatafilesToServer) {
        await this.applyDatafilesToServer();
      }
      this.hideCorridorEditPopup();
      this.clearCorridorEditHighlight();
      this.addStatusMessage({
        text: "Corridor deleted.",
        level: "success",
        ttlMs: 3000,
      });
    },

    showCorridorConfirmPopup(nodeId) {
      if (!this.map) {
        return;
      }
      const node = this.corridorPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      const popup = this.ensureCorridorEditPopup();
      const card = document.createElement("div");
      card.className = "vertiport-edit-card vertiport-edit-confirm";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Enter name";
      card.appendChild(title);
      const body = document.createElement("div");
      body.className = "vertiport-edit-confirm-body";
      card.appendChild(body);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions";
      card.appendChild(actions);

      const input = document.createElement("input");
      input.type = "text";
      input.className = "vertiport-edit-input";
      input.placeholder = "Name";
      body.appendChild(input);

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Cancel", () => {
          this.hideCorridorEditPopup();
        }),
      );
      actions.appendChild(
        buildButton("Save", () => {
          const value = input.value.trim();
          if (!value) {
            this.addStatusMessage({
              text: "Enter a name first.",
              level: "warn",
              ttlMs: 2500,
            });
            return;
          }
          void this.commitPendingCorridor(nodeId, value);
        }),
      );

      popup
        .setLngLat(node.lngLat)
        .setDOMContent(card)
        .addTo(this.map);
      this.corridorEditPopupNodeId = nodeId;
      this.corridorEditPopupName = null;
      input.focus();
    },

    async commitPendingCorridor(nodeId, name) {
      const node = this.corridorPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      const trimmed = String(name || "").trim();
      if (!trimmed) {
        this.addStatusMessage({
          text: "Enter a name first.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      if (this.corridorPointLookup && this.corridorPointLookup.has(trimmed)) {
        this.addStatusMessage({
          text: "Corridor name already exists.",
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const ready = await this.ensureEditableFile("corridor");
      if (!ready) {
        return;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.corridor &&
        this.fileControls.corridor.nameInput
          ? this.fileControls.corridor.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active corridor file.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const payload = {
        kind: "corridor",
        file: fileName,
        entry: {
          name: trimmed,
          lat: node.lngLat.lat,
          lon: node.lngLat.lng,
          alt_ft: 1000,
          link: "",
        },
      };
      const result = await this.requestDatafileAppend(payload);
      if (!result || !result.ok) {
        this.addStatusMessage({
          text: "Failed to append corridor data.",
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("corridor", nextName, { custom: true });
      this.config.data.waypointCsv = nextUrl;
      this.hideCorridorEditPopup();
      this.removePendingCorridorNode(nodeId);
      await this.loadCorridorTable(nextUrl);
      await this.loadCorridorOverlay();
      if (this.applyDatafilesToServer) {
        await this.applyDatafilesToServer();
      }
      this.addStatusMessage({
        text: "Corridor node saved.",
        level: "success",
        ttlMs: 3000,
      });
    },

    getCorridorPointIndexByName(name) {
      if (!name || !this.corridorHitData || !this.corridorHitData.points) {
        return -1;
      }
      const entry = this.corridorHitData.points.find((point) => point.name === name);
      return entry ? entry.index : -1;
    },

    updateCorridorEditSelection() {
      if (!this.corridorLayer || !this.corridorLayer.setSelectedPoint) {
        return;
      }
      const name = this.corridorEditHighlightName;
      const index = name ? this.getCorridorPointIndexByName(name) : -1;
      this.corridorLayer.setSelectedPoint(index);
      if (this.map) {
        this.map.triggerRepaint();
      }
    },

    setCorridorEditHighlight(name) {
      const next = name ? String(name) : "";
      if (this.corridorEditHighlightName === next) {
        return;
      }
      this.corridorEditHighlightName = next;
      this.updateCorridorEditSource();
      this.updateCorridorEditSelection();
    },

    clearCorridorEditHighlight() {
      if (!this.corridorEditHighlightName) {
        return;
      }
      this.corridorEditHighlightName = "";
      this.updateCorridorEditSource();
      this.updateCorridorEditSelection();
    },

    ensureVertiportEditGhost() {
      if (!this.map) {
        return;
      }
      this.ensureVertiportEditLayer();
    },

    showVertiportEditGhost(lngLat) {
      if (!this.map || !lngLat) {
        return;
      }
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return;
      }
      this.vertiportEditGhostLngLat = normalized;
      this.ensureVertiportEditLayer();
      this.updateVertiportEditSource();
    },

    hideVertiportEditGhost() {
      if (this.vertiportEditGhostLngLat) {
        this.vertiportEditGhostLngLat = null;
        this.updateVertiportEditSource();
      }
    },

    updateVertiportEditCoordLabel(point, lngLat) {
      if (!this.vertiportEditCoordLabel || !point || !lngLat) {
        return;
      }
      const lat = Number(lngLat.lat);
      const lon = Number(lngLat.lng);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        return;
      }
      this.vertiportEditCoordLabel.textContent = this.t("label.lat_lon", {
        lat: lat.toFixed(6),
        lon: lon.toFixed(6),
      });
      this.vertiportEditCoordLabel.style.left = `${point.x}px`;
      this.vertiportEditCoordLabel.style.top = `${point.y}px`;
      this.vertiportEditCoordLabel.classList.add("is-visible");
    },

    hideVertiportEditCoordLabel() {
      if (this.vertiportEditCoordLabel) {
        this.vertiportEditCoordLabel.classList.remove("is-visible");
      }
    },

    resolveMapPointer(event) {
      if (!this.map) {
        return { point: null, lngLat: null };
      }
      if (event && event.point) {
        return {
          point: event.point,
          lngLat: event.lngLat ? event.lngLat : this.map.unproject(event.point),
        };
      }
      const original = event && event.originalEvent ? event.originalEvent : null;
      const container = this.map.getCanvasContainer
        ? this.map.getCanvasContainer()
        : this.map.getCanvas();
      if (
        original &&
        container &&
        Number.isFinite(original.clientX) &&
        Number.isFinite(original.clientY)
      ) {
        const rect = container.getBoundingClientRect();
        const scaleX = rect.width ? container.clientWidth / rect.width : 1;
        const scaleY = rect.height ? container.clientHeight / rect.height : 1;
        const point = {
          x: (original.clientX - rect.left) * scaleX,
          y: (original.clientY - rect.top) * scaleY,
        };
        return { point, lngLat: this.map.unproject(point) };
      }
      return { point: null, lngLat: null };
    },

    handleVertiportEditHover(event) {
      if (!this.map || !this.isVertiportEditMode()) {
        this.hideVertiportEditGhost();
        this.hideVertiportEditCoordLabel();
        return false;
      }
      const { point, lngLat } = this.resolveMapPointer(event);
      if (this.vertiportEditMovingName) {
        if (lngLat) {
          this.showVertiportEditGhost(lngLat);
        } else {
          this.hideVertiportEditGhost();
        }
        this.clearVertiportHover();
        if (point && lngLat) {
          this.updateVertiportEditCoordLabel(point, lngLat);
        }
        this.map.getCanvas().style.cursor = "crosshair";
        return true;
      }
      if (this.vertiportEditMovingId) {
        const node = this.vertiportPendingNodes.get(this.vertiportEditMovingId);
        if (node && lngLat) {
          this.updatePendingVertiportNodePosition(node, lngLat);
        }
        this.hideVertiportEditGhost();
        this.clearVertiportHover();
        if (point && lngLat) {
          this.updateVertiportEditCoordLabel(point, lngLat);
        }
        this.map.getCanvas().style.cursor = "crosshair";
        return true;
      }
      if (this.vertiportLinking) {
        this.hideVertiportEditGhost();
        this.hideVertiportEditCoordLabel();
        this.clearVertiportHover();
        this.map.getCanvas().style.cursor = "crosshair";
        return true;
      }
      if (this.isVertiportNodeToolActive()) {
        if (point && this.pickVertiportAt(point)) {
          this.hideVertiportEditGhost();
          this.hideVertiportEditCoordLabel();
          return false;
        }
        if (lngLat) {
          this.showVertiportEditGhost(lngLat);
        }
        this.clearVertiportHover();
        if (point && lngLat) {
          this.updateVertiportEditCoordLabel(point, lngLat);
        }
        this.map.getCanvas().style.cursor = "crosshair";
        return true;
      }
      this.hideVertiportEditGhost();
      this.hideVertiportEditCoordLabel();
      return false;
    },

    handleVertiportEditClick(event) {
      if (!this.map || !this.isVertiportEditMode()) {
        return false;
      }
      const { point, lngLat } = this.resolveMapPointer(event);
      if (
        point &&
        this.shouldTriggerRepeatTapContext &&
        this.shouldTriggerRepeatTapContext("vertiport-edit", point)
      ) {
        const synthetic = this.buildSyntheticContextMenuEvent
          ? this.buildSyntheticContextMenuEvent(point, lngLat)
          : { point, lngLat, originalEvent: { preventDefault() {}, stopPropagation() {} } };
        this.handleVertiportEditContextMenu(synthetic);
        return true;
      }
      if (this.vertiportEditMovingName) {
        const targetName = this.vertiportEditMovingName;
        if (lngLat) {
          void this.updateExistingVertiportPosition(targetName, lngLat);
          this.vertiportEditMovingName = null;
          this.clearVertiportEditHighlight();
          this.hideVertiportEditGhost();
          this.hideVertiportEditCoordLabel();
        }
        return true;
      }
      if (this.vertiportEditMovingId) {
        const node = this.vertiportPendingNodes.get(this.vertiportEditMovingId);
        if (node && lngLat) {
          this.updatePendingVertiportNodePosition(node, lngLat);
        }
        this.vertiportEditMovingId = null;
        return true;
      }
      if (this.vertiportLinking) {
        if (point) {
          const pendingId = this.pickPendingCorridorAt(point);
          if (pendingId) {
            this.addStatusMessage({
              text: "Confirm the corridor node before linking.",
              level: "info",
              ttlMs: 2500,
            });
            return true;
          }
          const pickedName = this.pickCorridorAt(point);
          if (pickedName) {
            return this.handleVertiportLinkSelection(pickedName);
          }
        }
        return true;
      }
      if (!this.isVertiportNodeToolActive()) {
        return false;
      }
      if (point) {
        const pendingId = this.pickPendingVertiportAt(point);
        if (pendingId) {
          this.toggleVertiportPendingPopup(pendingId);
          return true;
        }
      }
      if (this.isTrafficHoverTarget && point && this.isTrafficHoverTarget(point)) {
        return true;
      }
      if (point) {
        const pickedName = this.pickVertiportAt(point);
        if (pickedName) {
          this.toggleVertiportExistingPopup(pickedName, lngLat);
          return true;
        }
      }
      if (lngLat) {
        this.createPendingVertiportNode(lngLat);
      }
      return true;
    },

    handleBaseStationEditClick(event) {
      if (!this.map || !this.isBaseStationEditMode()) {
        return false;
      }
      if (!this.isBaseStationNodeToolActive()) {
        return false;
      }
      if (event && event.baseStationHandled) {
        return true;
      }
      if (event) {
        event.baseStationHandled = true;
      }
      if (this.planState && this.planState.enabled) {
        return true;
      }
      const { point, lngLat } = this.resolveMapPointer(event);
      if (this.baseStationEditMovingName) {
        const targetName = this.baseStationEditMovingName;
        if (lngLat) {
          void this.updateExistingBaseStationPosition(targetName, lngLat);
          this.baseStationEditMovingName = null;
          this.clearBaseStationEditHighlight();
        }
        return true;
      }
      if (this.baseStationEditMovingId) {
        const node = this.baseStationPendingNodes.get(this.baseStationEditMovingId);
        if (node && lngLat) {
          this.updatePendingBaseStationNodePosition(node, lngLat);
        }
        this.baseStationEditMovingId = null;
        return true;
      }
      if (point) {
        const pendingId = this.pickPendingBaseStationAt(point);
        if (pendingId) {
          this.toggleBaseStationPendingPopup(pendingId);
          return true;
        }
      }
      if (this.isTrafficHoverTarget && point && this.isTrafficHoverTarget(point)) {
        return true;
      }
      if (point) {
        const pickedName = this.pickBaseStationAt(point);
        if (pickedName) {
          this.toggleBaseStationExistingPopup(pickedName, lngLat);
          return true;
        }
      }
      if (lngLat) {
        this.createPendingBaseStationNode(lngLat);
      }
      return true;
    },

    handleBaseStationEditContextMenu(event) {
      if (!this.map || !this.isBaseStationEditMode()) {
        return false;
      }
      if (this.scaleCopyActive) {
        return false;
      }
      const { point } = this.resolveMapPointer(event);
      if (!point) {
        return false;
      }
      const pendingId = this.pickPendingBaseStationAt(point);
      if (pendingId) {
        if (event && event.originalEvent) {
          if (event.originalEvent.preventDefault) {
            event.originalEvent.preventDefault();
          }
          if (event.originalEvent.stopPropagation) {
            event.originalEvent.stopPropagation();
          }
        }
        this.removePendingBaseStationNode(pendingId);
        return true;
      }
      const pickedName = this.pickBaseStationAt(point);
      if (!pickedName) {
        return false;
      }
      if (event && event.originalEvent) {
        if (event.originalEvent.preventDefault) {
          event.originalEvent.preventDefault();
        }
        if (event.originalEvent.stopPropagation) {
          event.originalEvent.stopPropagation();
        }
      }
      void this.deleteExistingBaseStation(pickedName);
      return true;
    },

    handleVertiportEditContextMenu(event) {
      if ((this.isEmergencyLandingMode && this.isEmergencyLandingMode()) ||
          (this.isForceMoveMode && this.isForceMoveMode())) {
        if (event && event.originalEvent) {
          if (event.originalEvent.preventDefault) {
            event.originalEvent.preventDefault();
          }
          if (event.originalEvent.stopPropagation) {
            event.originalEvent.stopPropagation();
          }
        }
        return true;
      }
      if (
        this.handleBaseStationEditContextMenu &&
        this.handleBaseStationEditContextMenu(event)
      ) {
        return true;
      }
      if (!this.map || !this.isVertiportEditMode()) {
        return false;
      }
      if (this.scaleCopyActive) {
        return false;
      }
      if (this.vertiportLinking) {
        if (event && event.originalEvent) {
          if (event.originalEvent.preventDefault) {
            event.originalEvent.preventDefault();
          }
          if (event.originalEvent.stopPropagation) {
            event.originalEvent.stopPropagation();
          }
        }
        this.clearVertiportLinking();
        return true;
      }
      const { point } = this.resolveMapPointer(event);
      if (!point) {
        return false;
      }
      const matrix =
        this.vertiportLinks3dLayer && this.vertiportLinks3dLayer.getMatrix
          ? this.vertiportLinks3dLayer.getMatrix()
          : null;
      if (matrix) {
        const target = this.findVertiportLinkHoverTarget(point, matrix);
        if (target && target.type === "line") {
          const line =
            this.vertiportData && this.vertiportData.lines
              ? this.vertiportData.lines[target.index]
              : null;
          if (line && line.from && line.to) {
            if (event && event.originalEvent) {
              if (event.originalEvent.preventDefault) {
                event.originalEvent.preventDefault();
              }
              if (event.originalEvent.stopPropagation) {
                event.originalEvent.stopPropagation();
              }
            }
            void this.removeVertiportLink(line.from, line.to);
            return true;
          }
        }
      }
      if (!this.isVertiportNodeToolActive()) {
        return false;
      }
      const pendingId = this.pickPendingVertiportAt(point);
      if (!pendingId) {
        return false;
      }
      if (event && event.originalEvent) {
        if (event.originalEvent.preventDefault) {
          event.originalEvent.preventDefault();
        }
        if (event.originalEvent.stopPropagation) {
          event.originalEvent.stopPropagation();
        }
      }
      this.removePendingVertiportNode(pendingId);
      return true;
    },

    ensureVertiportEditLayer() {
      if (!this.map) {
        return;
      }
      const sourceId = "vertiport-edit";
      if (!this.map.getSource(sourceId)) {
        this.map.addSource(sourceId, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!this.map.getLayer("vertiport-edit-circle")) {
        this.map.addLayer({
          id: "vertiport-edit-circle",
          type: "circle",
          source: sourceId,
          paint: {
            "circle-radius": [
              "case",
              ["==", ["get", "kind"], "ghost"],
              6 * MAP_SIZE_SCALE,
              7 * MAP_SIZE_SCALE,
            ],
            "circle-color": "#ffffff",
            "circle-stroke-color": [
              "case",
              ["==", ["get", "kind"], "ghost"],
              "#88a8c6",
              "#1b1b1b",
            ],
            "circle-stroke-width": [
              "case",
              ["==", ["get", "kind"], "ghost"],
              1.2 * MAP_SIZE_SCALE,
              1.6 * MAP_SIZE_SCALE,
            ],
            "circle-stroke-opacity": [
              "case",
              ["==", ["get", "kind"], "ghost"],
              0.5,
              1,
            ],
          },
        });
      }
      this.reorderPlanLayers();
      this.updateVertiportEditSource();
    },

    updateVertiportEditSource() {
      if (!this.map) {
        return;
      }
      const source = this.map.getSource("vertiport-edit");
      if (!source || !source.setData) {
        return;
      }
      const features = [];
      if (this.vertiportEditGhostLngLat) {
        features.push({
          type: "Feature",
          id: "ghost",
          geometry: {
            type: "Point",
            coordinates: [this.vertiportEditGhostLngLat.lng, this.vertiportEditGhostLngLat.lat],
          },
          properties: { kind: "ghost" },
        });
      }
      this.vertiportPendingNodes.forEach((node) => {
        if (!node || !node.lngLat) {
          return;
        }
        features.push({
          type: "Feature",
          id: node.id,
          geometry: {
            type: "Point",
            coordinates: [node.lngLat.lng, node.lngLat.lat],
          },
          properties: { kind: "pending", nodeId: node.id },
        });
      });
      source.setData({ type: "FeatureCollection", features });
    },

    pickPendingVertiportAt(point) {
      if (!this.map) {
        return null;
      }
      if (!this.map.getLayer("vertiport-edit-circle")) {
        return null;
      }
      const features = this.map.queryRenderedFeatures(point, {
        layers: ["vertiport-edit-circle"],
      });
      if (!features.length) {
        return null;
      }
      const target = features.find(
        (feature) => feature.properties && feature.properties.kind === "pending",
      );
      if (!target) {
        return null;
      }
      const props = target.properties || {};
      const id = props.nodeId || target.id;
      return id ? String(id) : null;
    },

    createPendingVertiportNode(lngLat) {
      if (!this.map || !lngLat) {
        return null;
      }
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return null;
      }
      const id = `pending-${(this.vertiportPendingCounter += 1)}`;
      const node = { id, lngLat: normalized };
      this.vertiportPendingNodes.set(id, node);
      this.ensureVertiportEditLayer();
      this.updateVertiportEditSource();
      return node;
    },

    updatePendingVertiportNodePosition(node, lngLat) {
      if (!node || !lngLat) {
        return;
      }
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return;
      }
      node.lngLat = normalized;
      this.updateVertiportEditSource();
    },

    removePendingVertiportNode(nodeId) {
      const node = this.vertiportPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      this.vertiportPendingNodes.delete(nodeId);
      this.updateVertiportEditSource();
      if (this.vertiportEditPopupNodeId === nodeId) {
        this.hideVertiportEditPopup();
      }
      if (this.vertiportEditMovingId === nodeId) {
        this.vertiportEditMovingId = null;
      }
    },

    ensureVertiportEditPopup() {
      if (this.vertiportEditPopup) {
        return this.vertiportEditPopup;
      }
      const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: true,
        className: "vertiport-edit-popup",
      });
      if (popup.on) {
        popup.on("close", () => {
          this.vertiportEditPopupNodeId = null;
          this.vertiportEditPopupName = null;
        });
      }
      this.vertiportEditPopup = popup;
      return popup;
    },

    hideVertiportEditPopup() {
      if (this.vertiportEditPopup) {
        this.vertiportEditPopup.remove();
      }
      this.vertiportEditPopupNodeId = null;
      this.vertiportEditPopupName = null;
    },

    toggleVertiportPendingPopup(nodeId) {
      if (!this.map) {
        return;
      }
      const node = this.vertiportPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      if (this.vertiportEditPopupNodeId === nodeId) {
        this.hideVertiportEditPopup();
        return;
      }
      const popup = this.ensureVertiportEditPopup();
      popup
        .setLngLat(node.lngLat)
        .setDOMContent(this.buildVertiportPendingPopupContent(nodeId))
        .addTo(this.map);
      this.vertiportEditPopupNodeId = nodeId;
      this.vertiportEditPopupName = null;
    },

    buildVertiportPendingPopupContent(nodeId) {
      const card = document.createElement("div");
      card.className = "vertiport-edit-card";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Vertiport Node";
      card.appendChild(title);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions vertiport-edit-actions-wide";

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Move", () => {
          this.vertiportEditMovingId = nodeId;
          this.hideVertiportEditPopup();
        }),
      );
      actions.appendChild(
        buildButton("Link", () => {
          this.addStatusMessage({
            text: "Confirm the node before linking.",
            level: "info",
            ttlMs: 2500,
          });
        }),
      );
      actions.appendChild(
        buildButton("Delete", () => {
          this.removePendingVertiportNode(nodeId);
        }),
      );
      actions.appendChild(
        buildButton("Confirm", () => {
          this.showVertiportConfirmPopup(nodeId);
        }),
      );
      card.appendChild(actions);
      return card;
    },

    toggleVertiportExistingPopup(name, lngLat) {
      if (!this.map) {
        return;
      }
      const entry = this.vertiportPointLookup ? this.vertiportPointLookup.get(name) : null;
      if (!entry) {
        return;
      }
      if (this.vertiportEditPopupName === name) {
        this.hideVertiportEditPopup();
        return;
      }
      const anchorLngLat =
        lngLat && Number.isFinite(lngLat.lng) && Number.isFinite(lngLat.lat)
          ? lngLat
          : { lng: entry.coord[0], lat: entry.coord[1] };
      const popup = this.ensureVertiportEditPopup();
      popup
        .setLngLat(anchorLngLat)
        .setDOMContent(this.buildVertiportExistingPopupContent(name))
        .addTo(this.map);
      this.vertiportEditPopupNodeId = null;
      this.vertiportEditPopupName = name;
    },

    buildVertiportExistingPopupContent(name) {
      const entry = this.vertiportPointLookup ? this.vertiportPointLookup.get(name) : null;
      const card = document.createElement("div");
      card.className = "vertiport-edit-card";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      const titleText =
        entry && entry.name
          ? this.t("label.vertiport_named", { name: entry.name })
          : this.translateLiteral("Vertiport");
      title.textContent = titleText;
      card.appendChild(title);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions vertiport-edit-actions-wide";

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Move", () => {
          if (!entry || !entry.coord) {
            return;
          }
          this.vertiportEditMovingName = name;
          this.setVertiportEditHighlight(name);
          this.vertiportEditGhostLngLat = { lng: entry.coord[0], lat: entry.coord[1] };
          this.ensureVertiportEditLayer();
          this.updateVertiportEditSource();
          this.hideVertiportEditPopup();
          this.addStatusMessage({
            text: "Click map to set new vertiport position.",
            level: "info",
            ttlMs: 3500,
          });
        }),
      );
      actions.appendChild(
        buildButton("Link", () => {
          this.startVertiportLinking(name);
        }),
      );
      actions.appendChild(
        buildButton("Edit", () => {
          this.showVertiportExistingEditPopup(name);
        }),
      );
      actions.appendChild(
        buildButton("Delete", () => {
          this.showVertiportExistingDeletePopup(name);
        }),
      );
      card.appendChild(actions);
      return card;
    },

    startVertiportLinking(name) {
      if (!name) {
        return;
      }
      this.clearVertiportLinking();
      if (this.ensureEditableFile) {
        void this.ensureEditableFile("vertiport");
      }
      const entry = this.vertiportPointLookup ? this.vertiportPointLookup.get(name) : null;
      if (!entry) {
        return;
      }
      this.vertiportLinking = { from: name, stage: "pick", busy: false };
      this.setVertiportEditHighlight(name);
      this.hideVertiportEditPopup();
      this.clearVertiportHover();
      this.addStatusMessage({
        text: this.t("status.select_corridor_target", { name }),
        level: "info",
        ttlMs: 3000,
      });
    },

    clearVertiportLinking() {
      if (!this.vertiportLinking) {
        if (!this.vertiportEditMovingName) {
          this.clearVertiportEditHighlight();
        }
        return;
      }
      this.vertiportLinking = null;
      if (!this.vertiportEditMovingName) {
        this.clearVertiportEditHighlight();
      }
    },

    handleVertiportLinkSelection(targetName) {
      if (!this.vertiportLinking || !this.vertiportLinking.from) {
        return false;
      }
      if (!targetName) {
        return false;
      }
      if (this.vertiportLinking.busy) {
        this.addStatusMessage({
          text: "Link update in progress.",
          level: "info",
          ttlMs: 2000,
        });
        return true;
      }
      if (targetName === this.vertiportLinking.from) {
        this.addStatusMessage({
          text: "Select a different corridor node.",
          level: "warn",
          ttlMs: 2500,
        });
        return true;
      }
      this.vertiportLinking.busy = true;
      void this.commitVertiportLink(this.vertiportLinking.from, targetName).finally(() => {
        if (this.vertiportLinking) {
          this.vertiportLinking.busy = false;
        }
      });
      return true;
    },

    getVertiportLinkList(name) {
      const lookup = this.vertiportLinkLookup;
      const list = lookup && lookup.get(name) ? lookup.get(name) : [];
      const seen = new Set();
      const cleaned = [];
      list.forEach((entry) => {
        const value = String(entry || "").trim();
        if (!value || seen.has(value)) {
          return;
        }
        seen.add(value);
        cleaned.push(value);
      });
      return cleaned;
    },

      async commitVertiportLink(fromName, targetName) {
        if (!this.vertiportPointLookup || !this.vertiportPointLookup.has(fromName)) {
          this.addStatusMessage({
            text: "Vertiport not found.",
            level: "warn",
            ttlMs: 2500,
          });
          this.clearVertiportLinking();
          return;
        }
        if (!this.corridorPointLookup || !this.corridorPointLookup.has(targetName)) {
          this.addStatusMessage({
            text: "Select a corridor node.",
            level: "warn",
            ttlMs: 2500,
          });
          return;
        }
        const links = this.getVertiportLinkList(fromName);
        if (links.includes(targetName)) {
          this.addStatusMessage({
            text: "Link already exists.",
            level: "info",
            ttlMs: 2500,
          });
          this.clearVertiportLinking();
          return;
        }
        const ok = await this.applyVertiportUpdate(
          fromName,
          { link_append: targetName },
          "Vertiport link updated.",
        );
        if (ok) {
          this.clearVertiportLinking();
        }
      },

      async removeVertiportLink(fromName, targetName) {
        if (!this.vertiportPointLookup || !this.vertiportPointLookup.has(fromName)) {
          this.addStatusMessage({
            text: "Vertiport not found.",
            level: "warn",
            ttlMs: 2500,
          });
          return;
        }
        await this.applyVertiportUpdate(
          fromName,
          { link_remove: targetName },
          "Vertiport link removed.",
        );
      },

    showVertiportExistingEditPopup(name) {
      if (!this.map) {
        return;
      }
      const entry = this.vertiportPointLookup ? this.vertiportPointLookup.get(name) : null;
      if (!entry) {
        return;
      }
      const popup = this.ensureVertiportEditPopup();
      const card = document.createElement("div");
      card.className = "vertiport-edit-card vertiport-edit-confirm";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Edit vertiport";
      card.appendChild(title);
      const body = document.createElement("div");
      body.className = "vertiport-edit-confirm-body";
      card.appendChild(body);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions";
      card.appendChild(actions);

      let pendingName = entry.name || name;
      let pendingClass = entry.className === "hub" ? "hub" : "port";

      const input = document.createElement("input");
      input.type = "text";
      input.className = "vertiport-edit-input";
      input.value = pendingName;
      input.placeholder = "Name";
      body.appendChild(input);

      const options = document.createElement("div");
      options.className = "vertiport-edit-options";
      const updateClassSelection = () => {
        Array.from(options.children).forEach((child) => {
          if (child instanceof HTMLElement) {
            child.classList.toggle("is-active", child.dataset.value === pendingClass);
          }
        });
      };
      const buildOption = (value, label) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-option";
        button.dataset.value = value;
        button.textContent = label;
        button.addEventListener("click", () => {
          pendingClass = value;
          updateClassSelection();
        });
        return button;
      };
      options.appendChild(buildOption("port", "port"));
      options.appendChild(buildOption("hub", "hub"));
      updateClassSelection();
      body.appendChild(options);

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Cancel", () => {
          this.hideVertiportEditPopup();
        }),
      );
      actions.appendChild(
        buildButton("Save", () => {
          const value = input.value.trim();
          if (!value) {
            this.addStatusMessage({
              text: "Enter a name first.",
              level: "warn",
              ttlMs: 2500,
            });
            return;
          }
          if (
            value !== name &&
            this.vertiportPointLookup &&
            this.vertiportPointLookup.has(value)
          ) {
            this.addStatusMessage({
              text: "Vertiport name already exists.",
              level: "warn",
              ttlMs: 3000,
            });
            return;
          }
          pendingName = value;
          void this.updateExistingVertiport(name, {
            name: pendingName,
            class: pendingClass,
          });
        }),
      );

      popup
        .setLngLat({ lng: entry.coord[0], lat: entry.coord[1] })
        .setDOMContent(card)
        .addTo(this.map);
      this.vertiportEditPopupNodeId = null;
      this.vertiportEditPopupName = name;
      input.focus();
    },

    showVertiportExistingDeletePopup(name) {
      if (!this.map) {
        return;
      }
      const entry = this.vertiportPointLookup ? this.vertiportPointLookup.get(name) : null;
      if (!entry) {
        return;
      }
      const popup = this.ensureVertiportEditPopup();
      const card = document.createElement("div");
      card.className = "vertiport-edit-card vertiport-edit-confirm";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      title.textContent = "Delete vertiport";
      card.appendChild(title);
      const body = document.createElement("div");
      body.className = "vertiport-edit-confirm-body";
      body.textContent = entry.name
        ? this.t("label.delete_vertiport_named", { name: entry.name })
        : this.t("label.delete_vertiport");
      card.appendChild(body);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions";
      card.appendChild(actions);

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      actions.appendChild(
        buildButton("Cancel", () => {
          this.hideVertiportEditPopup();
        }),
      );
      actions.appendChild(
        buildButton("Delete", () => {
          void this.deleteExistingVertiport(name);
        }),
      );

      popup
        .setLngLat({ lng: entry.coord[0], lat: entry.coord[1] })
        .setDOMContent(card)
        .addTo(this.map);
      this.vertiportEditPopupNodeId = null;
      this.vertiportEditPopupName = name;
    },

    async applyVertiportUpdate(targetName, updates, successText) {
      const name = String(targetName || "").trim();
      if (!name) {
        return false;
      }
      const ready = await this.ensureEditableFile("vertiport");
      if (!ready) {
        return false;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.vertiport &&
        this.fileControls.vertiport.nameInput
          ? this.fileControls.vertiport.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active vertiport file.",
          level: "warn",
          ttlMs: 2500,
        });
        return false;
      }
      const payload = {
        kind: "vertiport",
        file: fileName,
        target: name,
        updates: updates || {},
      };
      const result = await this.requestDatafileUpdate(payload);
      if (!result || !result.ok) {
        const message =
          result && typeof result.message === "string" && result.message
            ? result.message
            : "Failed to update vertiport.";
        this.addStatusMessage({
          text: message,
          level: "warn",
          ttlMs: 3000,
        });
        return false;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("vertiport", nextName, { custom: true });
      this.config.data.vertiportCsv = nextUrl;
      await this.loadVertiportTable(nextUrl);
      await this.loadVertiportOverlay();
      if (this.applyDatafilesToServer) {
        await this.applyDatafilesToServer();
      }
      if (this.vertiportZoneName && !this.vertiportPointLookup.has(this.vertiportZoneName)) {
        this.clearVertiportZone();
      }
      if (successText) {
        this.addStatusMessage({
          text: successText,
          level: "success",
          ttlMs: 3000,
        });
      }
      return true;
    },

    async updateExistingVertiportPosition(name, lngLat) {
      const normalized = this.normalizeLngLat(lngLat);
      if (!normalized) {
        return;
      }
      const ok = await this.applyVertiportUpdate(
        name,
        { lat: normalized.lat, lon: normalized.lng },
        "Vertiport position updated.",
      );
      if (ok) {
        this.hideVertiportEditPopup();
      }
    },

    async updateExistingVertiport(name, updates) {
      const payload = updates && typeof updates === "object" ? updates : {};
      const nextName =
        Object.prototype.hasOwnProperty.call(payload, "name") &&
        typeof payload.name === "string"
          ? payload.name.trim()
          : String(name || "").trim();
      if (!nextName) {
        this.addStatusMessage({
          text: "Enter a name first.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      if (
        nextName !== name &&
        this.vertiportPointLookup &&
        this.vertiportPointLookup.has(nextName)
      ) {
        this.addStatusMessage({
          text: "Vertiport name already exists.",
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      let normalizedClass = null;
      if (Object.prototype.hasOwnProperty.call(payload, "class")) {
        if (payload.class === "hub") {
          normalizedClass = "hub";
        } else if (payload.class === "port") {
          normalizedClass = "port";
        } else {
          this.addStatusMessage({
            text: "Invalid vertiport class.",
            level: "warn",
            ttlMs: 3000,
          });
          return;
        }
      }
      const updatesPayload = {};
      if (Object.prototype.hasOwnProperty.call(payload, "name")) {
        updatesPayload.name = nextName;
      }
      if (normalizedClass) {
        updatesPayload.class = normalizedClass;
      }
      const ok = await this.applyVertiportUpdate(name, updatesPayload, "Vertiport updated.");
      if (ok) {
        this.hideVertiportEditPopup();
      }
    },

    async deleteExistingVertiport(name) {
      const target = String(name || "").trim();
      if (!target) {
        return;
      }
      const ready = await this.ensureEditableFile("vertiport");
      if (!ready) {
        return;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.vertiport &&
        this.fileControls.vertiport.nameInput
          ? this.fileControls.vertiport.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active vertiport file.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const payload = {
        kind: "vertiport",
        file: fileName,
        target,
      };
      const result = await this.requestDatafileDelete(payload);
      if (!result || !result.ok) {
        const message =
          result && typeof result.message === "string" && result.message
            ? result.message
            : "Failed to delete vertiport.";
        this.addStatusMessage({
          text: message,
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("vertiport", nextName, { custom: true });
      this.config.data.vertiportCsv = nextUrl;
      await this.loadVertiportTable(nextUrl);
      await this.loadVertiportOverlay();
      if (this.applyDatafilesToServer) {
        await this.applyDatafilesToServer();
      }
      if (this.vertiportZoneName === target) {
        this.clearVertiportZone();
      }
      this.hideVertiportEditPopup();
      this.addStatusMessage({
        text: "Vertiport deleted.",
        level: "success",
        ttlMs: 3000,
      });
    },

    showVertiportConfirmPopup(nodeId) {
      if (!this.map) {
        return;
      }
      const node = this.vertiportPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      const popup = this.ensureVertiportEditPopup();
      const card = document.createElement("div");
      card.className = "vertiport-edit-card vertiport-edit-confirm";
      const title = document.createElement("div");
      title.className = "vertiport-edit-card-title";
      card.appendChild(title);
      const body = document.createElement("div");
      body.className = "vertiport-edit-confirm-body";
      card.appendChild(body);
      const actions = document.createElement("div");
      actions.className = "vertiport-edit-actions";
      card.appendChild(actions);

      let pendingName = "";
      let pendingClass = "port";

      const buildButton = (label, onClick) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "vertiport-edit-btn";
        button.textContent = label;
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onClick();
        });
        return button;
      };

      const renderNameStep = () => {
        title.textContent = "Enter name";
        body.innerHTML = "";
        actions.innerHTML = "";
        const input = document.createElement("input");
        input.type = "text";
        input.className = "vertiport-edit-input";
        input.value = pendingName;
        body.appendChild(input);
        actions.appendChild(
          buildButton("Cancel", () => {
            this.hideVertiportEditPopup();
          }),
        );
        actions.appendChild(
          buildButton("Next", () => {
            const value = input.value.trim();
            if (!value) {
              this.addStatusMessage({
                text: "Enter a name first.",
                level: "warn",
                ttlMs: 2500,
              });
              return;
            }
            pendingName = value;
            renderClassStep();
          }),
        );
        input.focus();
      };

      const renderClassStep = () => {
        title.textContent = "Select class";
        body.innerHTML = "";
        actions.innerHTML = "";
        const options = document.createElement("div");
        options.className = "vertiport-edit-options";

        const updateClassSelection = () => {
          Array.from(options.children).forEach((child) => {
            if (child instanceof HTMLElement) {
              child.classList.toggle("is-active", child.dataset.value === pendingClass);
            }
          });
        };
        const buildOption = (value, label) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "vertiport-edit-option";
          button.dataset.value = value;
          button.textContent = label;
          button.addEventListener("click", () => {
            pendingClass = value;
            updateClassSelection();
          });
          return button;
        };

        options.appendChild(buildOption("port", "port"));
        options.appendChild(buildOption("hub", "hub"));
        updateClassSelection();
        body.appendChild(options);

        actions.appendChild(buildButton("Back", renderNameStep));
        actions.appendChild(
          buildButton("Save", () => {
            this.commitPendingVertiport(nodeId, pendingName, pendingClass);
          }),
        );
      };

      renderNameStep();
      popup.setLngLat(node.lngLat).setDOMContent(card).addTo(this.map);
      this.vertiportEditPopupNodeId = nodeId;
    },

    getVertiportDefaultsByClass(className) {
      const defaults = {
        port: {
          inr_km: 1.4,
          otr_km: 0,
          mtr_km: 2.7,
          inr_deg: 165,
          otr_deg: 0,
          circle_turn: "Left",
        },
        hub: {
          inr_km: 1.4,
          otr_km: 2.7,
          mtr_km: 3.7,
          inr_deg: 45,
          otr_deg: 255,
          circle_turn: "Left",
        },
      };
      return defaults[className] || defaults.port;
    },

    async commitPendingVertiport(nodeId, name, className) {
      const node = this.vertiportPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      const trimmed = String(name || "").trim();
      if (!trimmed) {
        this.addStatusMessage({
          text: "Enter a name first.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      if (this.vertiportPointLookup && this.vertiportPointLookup.has(trimmed)) {
        this.addStatusMessage({
          text: "Vertiport name already exists.",
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const normalizedClass = className === "hub" ? "hub" : "port";
      const ready = await this.ensureEditableFile("vertiport");
      if (!ready) {
        return;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.vertiport &&
        this.fileControls.vertiport.nameInput
          ? this.fileControls.vertiport.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active vertiport file.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const defaults = this.getVertiportDefaultsByClass(normalizedClass);
      const payload = {
        kind: "vertiport",
        file: fileName,
        entry: {
          name: trimmed,
          class: normalizedClass,
          lat: node.lngLat.lat,
          lon: node.lngLat.lng,
          inr_km: defaults.inr_km,
          otr_km: defaults.otr_km,
          mtr_km: defaults.mtr_km,
          inr_deg: defaults.inr_deg,
          otr_deg: defaults.otr_deg,
          circle_turn: defaults.circle_turn,
          link: "",
        },
      };
      const result = await this.requestDatafileAppend(payload);
      if (!result || !result.ok) {
        this.addStatusMessage({
          text: "Failed to append vertiport data.",
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("vertiport", nextName, { custom: true });
      this.config.data.vertiportCsv = nextUrl;
      this.hideVertiportEditPopup();
      this.removePendingVertiportNode(nodeId);
      await this.loadVertiportTable(nextUrl);
      await this.loadVertiportOverlay();
      if (this.applyDatafilesToServer) {
        await this.applyDatafilesToServer();
      }
      this.addStatusMessage({
        text: "Vertiport node saved.",
        level: "success",
        ttlMs: 3000,
      });
    },

    async commitPendingBaseStation(nodeId, name) {
      const node = this.baseStationPendingNodes.get(nodeId);
      if (!node) {
        return;
      }
      const trimmed = String(name || "").trim();
      if (!trimmed) {
        this.addStatusMessage({
          text: "Enter a name first.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      if (this.baseStationPointLookup && this.baseStationPointLookup.has(trimmed)) {
        this.addStatusMessage({
          text: "Base station name already exists.",
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const ready = await this.ensureEditableFile("basestation");
      if (!ready) {
        return;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.basestation &&
        this.fileControls.basestation.nameInput
          ? this.fileControls.basestation.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active base station file.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const payload = {
        kind: "basestation",
        file: fileName,
        entry: {
          name: trimmed,
          lat: node.lngLat.lat,
          lon: node.lngLat.lng,
        },
      };
      const result = await this.requestDatafileAppend(payload);
      if (!result || !result.ok) {
        this.addStatusMessage({
          text: "Failed to append base station data.",
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("basestation", nextName, { custom: true });
      this.config.data.basestationCsv = nextUrl;
      await this.loadBaseStationOverlay(nextUrl, true);
      this.hideBaseStationEditPopup();
      this.removePendingBaseStationNode(nodeId);
      this.addStatusMessage({
        text: "Base station saved.",
        level: "success",
        ttlMs: 3000,
      });
    },

    async updateExistingBaseStationPosition(name, lngLat) {
      const target = String(name || "").trim();
      if (!target) {
        return;
      }
      const ready = await this.ensureEditableFile("basestation");
      if (!ready) {
        return;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.basestation &&
        this.fileControls.basestation.nameInput
          ? this.fileControls.basestation.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active base station file.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const payload = {
        kind: "basestation",
        file: fileName,
        target,
        updates: {
          lat: lngLat.lat,
          lon: lngLat.lng,
        },
      };
      const result = await this.requestDatafileUpdate(payload);
      if (!result || !result.ok) {
        const message =
          result && typeof result.message === "string" && result.message
            ? result.message
            : "Failed to update base station.";
        this.addStatusMessage({
          text: message,
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("basestation", nextName, { custom: true });
      this.config.data.basestationCsv = nextUrl;
      await this.loadBaseStationOverlay(nextUrl, true);
      this.hideBaseStationEditPopup();
      this.addStatusMessage({
        text: "Base station position updated.",
        level: "success",
        ttlMs: 3000,
      });
    },

    async deleteExistingBaseStation(name) {
      const target = String(name || "").trim();
      if (!target) {
        return;
      }
      const ready = await this.ensureEditableFile("basestation");
      if (!ready) {
        return;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.basestation &&
        this.fileControls.basestation.nameInput
          ? this.fileControls.basestation.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active base station file.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const payload = {
        kind: "basestation",
        file: fileName,
        target,
      };
      const result = await this.requestDatafileDelete(payload);
      if (!result || !result.ok) {
        const message =
          result && typeof result.message === "string" && result.message
            ? result.message
            : "Failed to delete base station.";
        this.addStatusMessage({
          text: message,
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("basestation", nextName, { custom: true });
      this.config.data.basestationCsv = nextUrl;
      await this.loadBaseStationOverlay(nextUrl, true);
      this.hideBaseStationEditPopup();
      this.addStatusMessage({
        text: "Base station deleted.",
        level: "success",
        ttlMs: 3000,
      });
    },

    async commitBaseStationAdd(lngLat) {
      const ready = await this.ensureEditableFile("basestation");
      if (!ready) {
        return;
      }
      const fileName =
        this.fileControls &&
        this.fileControls.basestation &&
        this.fileControls.basestation.nameInput
          ? this.fileControls.basestation.nameInput.value.trim()
          : "";
      if (!fileName) {
        this.addStatusMessage({
          text: "No active base station file.",
          level: "warn",
          ttlMs: 2500,
        });
        return;
      }
      const name = this.getNextBaseStationName();
      const payload = {
        kind: "basestation",
        file: fileName,
        entry: {
          name,
          lat: lngLat.lat,
          lon: lngLat.lng,
        },
      };
      const result = await this.requestDatafileAppend(payload);
      if (!result || !result.ok) {
        this.addStatusMessage({
          text: "Failed to append base station data.",
          level: "warn",
          ttlMs: 3000,
        });
        return;
      }
      const nextName = typeof result.name === "string" ? result.name : fileName;
      const nextUrl =
        typeof result.url === "string" && result.url
          ? result.url.replace(/^\/+/, "")
          : `api/data/customed/${nextName}`;
      this.updatePanelFileName("basestation", nextName, { custom: true });
      this.config.data.basestationCsv = nextUrl;
      await this.loadBaseStationOverlay(nextUrl, true);
      this.addStatusMessage({
        text: "Base station saved.",
        level: "success",
        ttlMs: 3000,
      });
    },

    setupVertiportHover() {
      if (!this.map) {
        return;
      }
      const label = document.createElement("div");
      label.className = "vertiport-hover-label";
      this.map.getContainer().appendChild(label);
      this.vertiportHoverLabel = label;

      const coordLabel = document.createElement("div");
      coordLabel.className = "vertiport-edit-coord";
      this.map.getContainer().appendChild(coordLabel);
      this.vertiportEditCoordLabel = coordLabel;

      this.map.on("mousemove", (event) => this.handleVertiportHover(event));
      this.map.on("mouseleave", () => this.clearVertiportHover());
      this.map.on("movestart", () => this.clearVertiportHover());
      this.map.on("dragstart", () => this.clearVertiportHover());
      this.map.on("zoomstart", () => this.clearVertiportHover());
      this.map.on("pitchstart", () => this.clearVertiportHover());
      this.map.on("rotatestart", () => this.clearVertiportHover());
    },

    setupVertiportZoneClick() {
      if (!this.map) {
        return;
      }
      this.map.on("click", (event) => this.handleVertiportZoneClick(event));
      this.map.on("contextmenu", (event) => this.handleVertiportContextMenu(event));
    },

    handleVertiportZoneClick(event) {
      if (!this.map) {
        return;
      }
      if (this.handleEmergencyLandingClick && this.handleEmergencyLandingClick(event)) {
        return;
      }
      if (this.handleForceMoveClick && this.handleForceMoveClick(event)) {
        return;
      }
      if (this.handleBaseStationEditClick && this.handleBaseStationEditClick(event)) {
        return;
      }
      if (this.isAirspaceEditMode && this.isAirspaceEditMode()) {
        return;
      }
      if (this.handleVertiportEditClick(event)) {
        return;
      }
      const name = this.pickVertiportAt(event.point);
      if (!name) {
        return;
      }
      if (this.vertiportZoneName === name) {
        this.clearVertiportZone();
        return;
      }
      this.setVertiportZone(name);
    },

    handleVertiportContextMenu(event) {
      if (
        this.handleVertiportEditContextMenu &&
        this.handleVertiportEditContextMenu(event)
      ) {
        return;
      }
      this.handleVertiportManageContextMenu(event);
    },

    handleVertiportManageContextMenu(event) {
      if (!this.map) {
        return false;
      }
      if (this.isVertiportEditMode && this.isVertiportEditMode()) {
        return false;
      }
      if (this.isAirspaceEditMode && this.isAirspaceEditMode()) {
        return false;
      }
      const { point } = this.resolveMapPointer(event);
      if (!point) {
        return false;
      }
      if (this.isTrafficHoverTarget && this.isTrafficHoverTarget(point)) {
        return false;
      }
      const name = this.pickVertiportAt(point);
      if (!name) {
        return false;
      }
      if (event && event.originalEvent) {
        if (event.originalEvent.preventDefault) {
          event.originalEvent.preventDefault();
        }
        if (event.originalEvent.stopPropagation) {
          event.originalEvent.stopPropagation();
        }
      }
      const isSameTarget = this.vertiportManageName === name;
      const isOpen =
        this.vertiportManagePopup &&
        this.vertiportManagePopup.isOpen &&
        this.vertiportManagePopup.isOpen();
      if (isSameTarget && isOpen) {
        this.hideVertiportManagePopup();
        return true;
      }
      this.showVertiportManagePopup(name);
      return true;
    },

    ensureVertiportManagePopup() {
      if (!this.map) {
        return null;
      }
      if (this.vertiportManagePopup) {
        return this.vertiportManagePopup;
      }
      const popup = new maplibregl.Popup({
        closeButton: true,
        closeOnClick: true,
        className: "vertiport-manage-popup",
        anchor: "top",
        offset: [0, 16 * MAP_SIZE_SCALE],
        maxWidth: "none",
      });
      if (popup.on) {
        popup.on("close", () => {
          this.vertiportManageName = null;
        });
      }
      this.vertiportManagePopup = popup;
      return popup;
    },

    hideVertiportManagePopup() {
      if (this.vertiportManagePopup) {
        this.vertiportManagePopup.remove();
      }
      this.vertiportManageName = null;
    },

    buildVertiportScheduleTemplate(entry) {
      const links = entry && Array.isArray(entry.links) ? entry.links.filter(Boolean) : [];
      const firstLink = links.length ? links[0] : "-";
      const secondLink = links.length > 1 ? links[1] : "-";
      const gateRows = [
        { stand: "Gate-01", dep: "--:--", arr: "--:--", status: "Standby", route: firstLink },
        { stand: "Gate-02", dep: "--:--", arr: "--:--", status: "Standby", route: secondLink },
      ];
      const fatoRows = [
        { stand: "FATO-1", dep: "--:--", arr: "--:--", status: "Ready", route: firstLink },
        { stand: "FATO-2", dep: "--:--", arr: "--:--", status: "Ready", route: secondLink },
      ];
      return { gateRows, fatoRows };
    },

    appendVertiportScheduleBlock(container, titleText, rows) {
      const section = document.createElement("section");
      section.className = "vertiport-manage-schedule-section";
      const title = document.createElement("h4");
      title.className = "vertiport-manage-schedule-title";
      title.textContent = titleText;
      section.appendChild(title);

      const table = document.createElement("table");
      table.className = "vertiport-manage-schedule-table";
      const thead = document.createElement("thead");
      const headRow = document.createElement("tr");
      ["Stand", "DEP", "ARR", "Status"].forEach((label) => {
        const th = document.createElement("th");
        th.textContent = label;
        headRow.appendChild(th);
      });
      thead.appendChild(headRow);
      table.appendChild(thead);

      const tbody = document.createElement("tbody");
      (rows || []).forEach((row) => {
        const tr = document.createElement("tr");
        [row.stand, row.dep, row.arr, row.status].forEach((value, index) => {
          const td = document.createElement("td");
          td.textContent = value;
          if (index === 3 && String(value).toLowerCase() === "standby") {
            td.className = "is-standby";
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      section.appendChild(table);
      container.appendChild(section);
    },

    buildVertiportManagePopupContent(entry) {
      const card = document.createElement("div");
      card.className = "vertiport-manage-card";

      const left = document.createElement("section");
      left.className = "vertiport-manage-pane vertiport-manage-pane-info";
      const heading = document.createElement("div");
      heading.className = "vertiport-manage-heading";
      const title = document.createElement("h3");
      title.className = "vertiport-manage-title";
      title.textContent = entry && entry.name ? entry.name : "-";
      heading.appendChild(title);
      const badge = document.createElement("span");
      badge.className = "vertiport-manage-badge";
      badge.textContent = entry && entry.className ? String(entry.className).toUpperCase() : "PORT";
      heading.appendChild(badge);
      left.appendChild(heading);

      const infoGrid = document.createElement("div");
      infoGrid.className = "vertiport-manage-info-grid";
      const lat = entry && entry.coord && Number.isFinite(entry.coord[1]) ? entry.coord[1] : null;
      const lon = entry && entry.coord && Number.isFinite(entry.coord[0]) ? entry.coord[0] : null;
      const mtr = entry && Number.isFinite(entry.mtr_km) ? entry.mtr_km : null;
      const links = entry && Array.isArray(entry.links) ? entry.links.filter(Boolean) : [];
      const rows = [
        ["Latitude", lat != null ? lat.toFixed(6) : "-"],
        ["Longitude", lon != null ? lon.toFixed(6) : "-"],
        ["MTR Radius", mtr != null ? `${mtr.toFixed(1)} km` : "-"],
        ["Linked Nodes", links.length ? String(links.length) : "0"],
        ["Primary Link", links.length ? links[0] : "-"],
      ];
      rows.forEach(([labelText, valueText]) => {
        const label = document.createElement("div");
        label.className = "vertiport-manage-info-label";
        label.textContent = labelText;
        const value = document.createElement("div");
        value.className = "vertiport-manage-info-value";
        value.textContent = valueText;
        infoGrid.appendChild(label);
        infoGrid.appendChild(value);
      });
      left.appendChild(infoGrid);

      const hint = document.createElement("div");
      hint.className = "vertiport-manage-hint";
      hint.textContent = "Info panel (left) + schedule panel (right)";
      left.appendChild(hint);
      card.appendChild(left);

      const right = document.createElement("section");
      right.className = "vertiport-manage-pane vertiport-manage-pane-schedule";
      const rightTitle = document.createElement("h3");
      rightTitle.className = "vertiport-manage-schedule-heading";
      rightTitle.textContent = "Arrival / Departure Schedule";
      right.appendChild(rightTitle);
      const template = this.buildVertiportScheduleTemplate(entry);
      this.appendVertiportScheduleBlock(right, "Gate", template.gateRows);
      this.appendVertiportScheduleBlock(right, "FATO", template.fatoRows);
      card.appendChild(right);

      return card;
    },

    showVertiportManagePopup(name) {
      if (!this.map || !name || !this.vertiportPointLookup) {
        return;
      }
      const entry = this.vertiportPointLookup.get(name);
      if (!entry || !entry.coord) {
        return;
      }
      const popup = this.ensureVertiportManagePopup();
      if (!popup) {
        return;
      }
      popup
        .setLngLat(entry.coord)
        .setDOMContent(this.buildVertiportManagePopupContent(entry))
        .addTo(this.map);
      this.vertiportManageName = name;
    },

    ensureVertiportZoneLayer() {
      if (!this.map) {
        return;
      }
      if (!this.map.getSource("vertiport-zone")) {
        this.map.addSource("vertiport-zone", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      const beforeId = this.map.getLayer("vertiport-circle") ? "vertiport-circle" : undefined;
      if (!this.map.getLayer("vertiport-zone-fill")) {
        this.map.addLayer(
          {
            id: "vertiport-zone-fill",
            type: "fill",
            source: "vertiport-zone",
            paint: {
              "fill-color": VERTIPORT_ZONE_FILL,
              "fill-opacity": 0.75,
            },
          },
          beforeId,
        );
      }
      if (!this.map.getLayer("vertiport-zone-outline")) {
        this.map.addLayer(
          {
            id: "vertiport-zone-outline",
            type: "line",
            source: "vertiport-zone",
            paint: {
              "line-color": VERTIPORT_ZONE_STROKE,
              "line-width": VERTIPORT_ZONE_STROKE_WIDTH,
            },
          },
          beforeId,
        );
      }
      this.reorderPlanLayers();
    },

    setVertiportZone(name) {
      if (!this.map) {
        return;
      }
      const entry = name ? this.vertiportPointLookup.get(name) : null;
      if (!entry || !entry.coord) {
        return;
      }
      const radiusKm = Number(entry.mtr_km);
      if (!Number.isFinite(radiusKm) || radiusKm <= 0) {
        return;
      }
      const coords = buildCirclePolygon(entry.coord[0], entry.coord[1], radiusKm);
      if (!coords || coords.length < 4) {
        return;
      }
      this.ensureVertiportZoneLayer();
      const source = this.map.getSource("vertiport-zone");
      if (source && source.setData) {
        source.setData({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: { type: "Polygon", coordinates: [coords] },
              properties: { name },
            },
          ],
        });
        this.vertiportZoneName = name;
      }
    },

    clearVertiportZone() {
      if (!this.map || !this.map.getSource("vertiport-zone")) {
        this.vertiportZoneName = null;
        this.hideVertiportManagePopup();
        return;
      }
      const source = this.map.getSource("vertiport-zone");
      if (source && source.setData) {
        source.setData({ type: "FeatureCollection", features: [] });
      }
      this.vertiportZoneName = null;
      this.hideVertiportManagePopup();
    },

    handleVertiportHover(event) {
      if (!this.map) {
        return;
      }
      if ((this.isEmergencyLandingMode && this.isEmergencyLandingMode()) ||
          (this.isForceMoveMode && this.isForceMoveMode())) {
        this.hideVertiportEditGhost();
        this.hideVertiportEditCoordLabel();
      } else if (this.handleVertiportEditHover(event)) {
        return;
      }
      if (this.isTrafficHoverTarget && this.isTrafficHoverTarget(event.point)) {
        this.clearVertiportHover();
        return;
      }
      const restrictToPorts = this.isPlanSelectingPorts();
      if (this.corridorHover) {
        this.clearVertiportHover();
        return;
      }
      const pointLayers = [];
      if (this.map.getLayer("vertiport-icon")) {
        pointLayers.push("vertiport-icon");
      }
      if (this.map.getLayer("vertiport-circle")) {
        pointLayers.push("vertiport-circle");
      }
      if (pointLayers.length) {
        const features = this.map.queryRenderedFeatures(event.point, {
          layers: pointLayers,
        });
        if (features.length) {
          const feature = features[0];
          const name = feature && feature.properties ? String(feature.properties.name || "") : "";
          if (name) {
            const id = feature.id != null ? feature.id : name;
            if (this.vertiportLinkHoverId != null) {
              this.setVertiportLinkHoverState(null);
            }
            this.setVertiportLinkHoverIndex(-1);
            if (this.vertiportHoverId !== id) {
              this.setVertiportHoverState(id);
            }
            this.setVertiportHoverFilter(name);
            this.vertiportHover = { id, name };
            this.vertiportLinkHover = null;
            this.showVertiportLabel(`V : ${name}`, event.point);
            this.map.getCanvas().style.cursor = "pointer";
            return;
          }
        }
      }

      if (
        !restrictToPorts &&
        this.vertiportLinks3dLayer &&
        this.vertiportLinks3dLayer.getMatrix
      ) {
        const matrix = this.vertiportLinks3dLayer.getMatrix();
        if (matrix) {
          const target = this.findVertiportLinkHoverTarget(event.point, matrix);
          if (target && target.name) {
            if (this.vertiportHoverId != null) {
              this.setVertiportHoverState(null);
            }
            if (target.id != null && this.vertiportLinkHoverId !== target.id) {
              this.setVertiportLinkHoverState(target.id);
            }
            this.setVertiportLinkHoverIndex(target.index);
            this.setVertiportHoverFilter(null);
            this.vertiportHover = null;
            this.vertiportLinkHover = { id: target.id, name: target.name, index: target.index };
            this.showVertiportLabel(`VL : ${target.name}`, event.point);
            this.map.getCanvas().style.cursor = "pointer";
            return;
          }
        }
      }

      this.clearVertiportHover();
    },

    setVertiportHoverState(nextId) {
      if (!this.map) {
        return;
      }
      const sourceId = "vertiport-points";
      if (this.map.isStyleLoaded() && this.map.getSource(sourceId) && this.vertiportHoverId != null) {
        this.map.setFeatureState(
          { source: sourceId, id: this.vertiportHoverId },
          { hover: false },
        );
      }
      if (this.map.isStyleLoaded() && this.map.getSource(sourceId) && nextId != null) {
        this.map.setFeatureState({ source: sourceId, id: nextId }, { hover: true });
      }
      this.vertiportHoverId = nextId;
    },

    setVertiportLinkHoverState(nextId) {
      if (!this.map) {
        return;
      }
      const sourceId = "vertiport-links";
      if (
        this.map.isStyleLoaded() &&
        this.map.getSource(sourceId) &&
        this.vertiportLinkHoverId != null
      ) {
        this.map.setFeatureState(
          { source: sourceId, id: this.vertiportLinkHoverId },
          { hover: false },
        );
      }
      if (this.map.isStyleLoaded() && this.map.getSource(sourceId) && nextId != null) {
        this.map.setFeatureState({ source: sourceId, id: nextId }, { hover: true });
      }
      this.vertiportLinkHoverId = nextId;
    },

    setVertiportLinkHoverIndex(nextIndex) {
      const index = Number.isFinite(nextIndex) ? nextIndex : -1;
      if (index === this.vertiportLinkHoverIndex) {
        return;
      }
      this.vertiportLinkHoverIndex = index;
      if (this.vertiportLinks3dLayer && this.vertiportLinks3dLayer.setHoverLine) {
        let mapped = index;
        if (this.vertiportLinkDashIndex && index > -1) {
          const dashIndex = this.vertiportLinkDashIndex[index];
          if (dashIndex != null) {
            mapped = dashIndex;
          }
        }
        this.vertiportLinks3dLayer.setHoverLine(mapped);
      }
      if (this.map) {
        this.map.triggerRepaint();
      }
    },

    showVertiportLabel(text, point) {
      if (!this.vertiportHoverLabel) {
        return;
      }
      this.vertiportHoverLabel.textContent = text;
      this.vertiportHoverLabel.style.left = `${point.x}px`;
      this.vertiportHoverLabel.style.top = `${point.y}px`;
      this.vertiportHoverLabel.classList.add("is-visible");
    },

    clearVertiportHover() {
      if (!this.map) {
        return;
      }
      if (
        this.vertiportHoverId != null &&
        this.map.isStyleLoaded() &&
        this.map.getSource("vertiport-points")
      ) {
        this.map.setFeatureState(
          { source: "vertiport-points", id: this.vertiportHoverId },
          { hover: false },
        );
      }
      if (
        this.vertiportLinkHoverId != null &&
        this.map.isStyleLoaded() &&
        this.map.getSource("vertiport-links")
      ) {
        this.map.setFeatureState(
          { source: "vertiport-links", id: this.vertiportLinkHoverId },
          { hover: false },
        );
      }
      this.setVertiportLinkHoverIndex(-1);
      this.vertiportHover = null;
      this.vertiportHoverId = null;
      this.vertiportLinkHover = null;
      this.vertiportLinkHoverId = null;
      this.setVertiportHoverFilter(null);
      if (this.vertiportHoverLabel) {
        this.vertiportHoverLabel.classList.remove("is-visible");
      }
      this.hideVertiportEditCoordLabel();
      if ((this.isEmergencyLandingMode && this.isEmergencyLandingMode()) ||
          (this.isForceMoveMode && this.isForceMoveMode())) {
        this.map.getCanvas().style.cursor = "crosshair";
      } else if (!this.corridorHover) {
        this.map.getCanvas().style.cursor = "";
      }
    },

    setupTerrainToggle() {
      const baseThreshold = Number(this.config.dem.pitchThreshold);
      const enableThreshold = Number.isFinite(this.config.dem.pitchEnableThreshold)
        ? Number(this.config.dem.pitchEnableThreshold)
        : (Number.isFinite(baseThreshold) ? baseThreshold : 6);
      const disableThreshold = Number.isFinite(this.config.dem.pitchDisableThreshold)
        ? Math.min(Number(this.config.dem.pitchDisableThreshold), enableThreshold)
        : Math.max(0, enableThreshold - 3);
      const updateTerrain = () => {
        const pitch = Number(this.map.getPitch());
        const nextThreshold = this.terrainEnabled ? disableThreshold : enableThreshold;
        const shouldEnable = Number.isFinite(pitch) && pitch >= nextThreshold;
        if (shouldEnable === this.terrainEnabled) {
          return;
        }
        if (shouldEnable) {
          if (this.map.getSource("dem")) {
            this.map.setTerrain({
              source: "dem",
              exaggeration: this.config.dem.exaggeration,
            });
          }
        } else {
          this.map.setTerrain(null);
        }
        this.terrainEnabled = shouldEnable;
        this.updateHillshadeVisibility();
      };

      this.map.on("load", () => {
        updateTerrain();
        this.map.on("pitch", updateTerrain);
      });
    },

    isPlanSelectingPorts() {
      return this.planState.enabled && this.planState.selection.length < 2;
    },

    setPlanRoute(path) {
      if (!this.map || !this.map.getSource("flight-plan-route")) {
        return;
      }
      const coords = path
        .map((name) => this.routeNodeLookup.get(name))
        .filter(Boolean)
        .map((entry) => entry.coord);
      const features =
        coords.length >= 2
          ? [
              {
                type: "Feature",
                geometry: { type: "LineString", coordinates: coords },
                properties: {},
              },
            ]
          : [];
      this.map.getSource("flight-plan-route").setData({
        type: "FeatureCollection",
        features,
      });
      this.setPlanRoute3dPositions(path);
    },

    clearPlanRoute() {
      if (this.map && this.map.getSource("flight-plan-route")) {
        this.map.getSource("flight-plan-route").setData({
          type: "FeatureCollection",
          features: [],
        });
      }
      this.setPlanRoute3dPositions([]);
    },

    setPlanRoute3dPositions(path) {
      if (!this.planLayersReady) {
        this.ensurePlanLayers();
      }
      if (!this.planRouteLayer3d || !this.planRouteLayer3d.updatePositions || !this.map) {
        return;
      }
      const positions = [];
      path.forEach((name) => {
        const entry = this.routeNodeLookup.get(name);
        if (!entry) {
          return;
        }
        const altitude = this.resolveNodeAltitude(name);
        const merc = maplibregl.MercatorCoordinate.fromLngLat(entry.coord, altitude);
        positions.push(merc.x, merc.y, merc.z);
      });
      this.planRouteLayer3d.updatePositions(positions);
      this.map.triggerRepaint();
    },

    updateVertiportLinks3dLayer(data) {
      if (!this.planLayersReady) {
        this.ensurePlanLayers();
      }
      if (!this.vertiportLinks3dLayer || !this.map) {
        return;
      }
      const unitsPerPixel = this.getMercatorUnitsPerPixel();
      if (!Number.isFinite(unitsPerPixel) || unitsPerPixel <= 0) {
        this.scheduleVertiportLinkUpdate();
        return;
      }
      const laneSizing = this.getLinkLaneSizing(VERTIPORT_LINK_WIDTH_3D);
      const halfWidth = (laneSizing.laneWidth * unitsPerPixel) / 2;
      const positions = [];
      const dashIndex = [];
      let segmentIndex = 0;
      const dashOn = Math.max(1, VERTIPORT_LINK_DASH_ON_M);
      const dashOff = Math.max(1, VERTIPORT_LINK_DASH_OFF_M);
      const dashCycle = dashOn + dashOff;
      const appendSegment = (sx, sy, sz, ex, ey, ez) => {
        if (!halfWidth) {
          return;
        }
        const start = { x: sx, y: sy, z: sz };
        const end = { x: ex, y: ey, z: ez };
        this.appendCrossSegmentPositions(positions, start, end, halfWidth);
      };
      data.lines.forEach((line, lineIndex) => {
        const startAlt = line.start.altitude_m ?? 0;
        const endAlt = line.end.altitude_m ?? 0;
        const startCoord = line.start.coord;
        const endCoord = line.end.coord;
        if (!startCoord || !endCoord) {
          return;
        }
        const start = maplibregl.MercatorCoordinate.fromLngLat(startCoord, startAlt);
        const end = maplibregl.MercatorCoordinate.fromLngLat(endCoord, endAlt);
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const dz = end.z - start.z;
        const length_m = computeDistanceMeters(
          startCoord[0],
          startCoord[1],
          endCoord[0],
          endCoord[1],
        );
        dashIndex[lineIndex] = segmentIndex;
        if (!Number.isFinite(length_m) || length_m <= dashOn) {
          appendSegment(start.x, start.y, start.z, end.x, end.y, end.z);
          segmentIndex += 1;
          return;
        }
        let traveled = 0;
        while (traveled < length_m) {
          const segStart = traveled;
          const segEnd = Math.min(traveled + dashOn, length_m);
          const t0 = segStart / length_m;
          const t1 = segEnd / length_m;
          const sx = start.x + dx * t0;
          const sy = start.y + dy * t0;
          const sz = start.z + dz * t0;
          const ex = start.x + dx * t1;
          const ey = start.y + dy * t1;
          const ez = start.z + dz * t1;
          appendSegment(sx, sy, sz, ex, ey, ez);
          segmentIndex += 1;
          traveled += dashCycle;
        }
      });
      if (this.vertiportLinks3dLayer.updatePositions) {
        this.vertiportLinks3dLayer.updatePositions(positions);
      }
      this.vertiportLinkDashIndex = dashIndex;
      this.map.triggerRepaint();
    },

    scheduleVertiportLinkUpdate() {
      if (this.vertiportLinkUpdateScheduled) {
        return;
      }
      this.vertiportLinkUpdateScheduled = true;
      requestAnimationFrame(() => {
        this.vertiportLinkUpdateScheduled = false;
        if (this.vertiportData) {
          this.updateVertiportLinks3dLayer(this.vertiportData);
        }
      });
    },

    setupVertiportLinkResize() {
      if (!this.map || this.vertiportLinkResizeBound) {
        return;
      }
      this.vertiportLinkResizeBound = true;
      const update = () => this.scheduleVertiportLinkUpdate();
      this.map.on("zoomend", update);
      this.map.on("resize", update);
    }

});


