# Mission ICD v1 Final

## 1. Purpose

This document defines the finalized `Mission ICD v1` flight plan data structure.

The scope of this document is a single flight plan JSON record. The top-level structure is fixed to the following five sections:

- `flightPlanNumber`
- `aircraftId`
- `departure`
- `enRoute`
- `arrival`

The recommended transport form is a single JSON object. If multiple records are required, wrap them in an array at a higher level.

## 2. Review Notes

The overall direction of the finalized schema is appropriate. However, the following items should be fixed at the document level before implementation.

### 2.1 Normalization Rules Applied

- `departure.vertiport` and `arrival.vertiport` use the same key name, but must remain nested inside their respective sections.
- The canonical variable name for `EIBT (Gate In)` is `eibt`.
- The canonical variable name for `ELDT (Landing)` is `eldt`.
- The canonical variable name for `Center_LLA` is `centerLLA`.
- The unit of `LLA.alt` is fixed to `m`.
- The unit of `targetSpeed` is fixed to `m/s`, aligned with the current AirSim/SITL implementation basis.

### 2.2 Implementation Notes

- All time fields should use the same clock basis and the `HH:MM:SS` string format.
- `enRoute` must be an array sorted in ascending `seq`.
- As a rule, the `endLLA` of the previous segment should connect continuously to the `startLLA` of the next segment.
- Turn segments are limited to cases where `phase` is `D` or `H`.
- Non-turn segments normally use `A`, `B`, `C`, `E`, `F`, `G`, `I`, and `J`.
- If `K` is included later, it should use the same structure as other non-turn segments.

## 3. Canonical JSON Structure

The following is a compact example intended to show the field shape quickly. For the full `A~K` mission profile example, see section `7.1`.

```json
{
  "flightPlanNumber": 1201,
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "Yeouido",
    "std": "09:00:00",
    "depGateNumber": "G3",
    "eobt": "09:02:00",
    "depFatoNumber": "F2",
    "etot": "09:10:00"
  },
  "enRoute": [
    {
      "seq": 1,
      "phase": "C",
      "startLLA": {"lat": 37.480790, "lon": 126.878697, "alt": 50},
      "endLLA": {"lat": 37.480790, "lon": 126.884000, "alt": 300},
      "targetSpeed": 40
    },
    {
      "seq": 2,
      "phase": "D",
      "startLLA": {"lat": 37.480790, "lon": 126.884000, "alt": 300},
      "endLLA": {"lat": 37.476500, "lon": 126.889500, "alt": 300},
      "targetSpeed": 60,
      "turnDirection": "CW",
      "centerLLA": {"lat": 37.478000, "lon": 126.887500, "alt": 300}
    }
  ],
  "arrival": {
    "vertiport": "Jamsil",
    "sta": "10:00:00",
    "arrGateNumber": "G1",
    "eibt": "09:58:00",
    "arrFatoNumber": "F1",
    "eldt": "09:50:00"
  }
}
```

## 4. Field Definitions

### 4.1 Top-Level Fields

| Field | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `flightPlanNumber` | integer | Y | `1201` | Flight plan identifier |
| `aircraftId` | string | Y | `UAM0001` | Aircraft identifier |
| `departure` | object | Y | - | Departure information |
| `enRoute` | array | Y | - | Route segment array |
| `arrival` | object | Y | - | Arrival information |

### 4.2 `departure`

| Field | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `vertiport` | string | Y | `Yeouido` | Departure vertiport |
| `std` | string | Y | `09:00:00` | Scheduled Time of Departure |
| `depGateNumber` | string | Y | `G3` | Departure gate number |
| `eobt` | string | Y | `09:02:00` | Estimated Off-Block Time |
| `depFatoNumber` | string | Y | `F2` | Departure FATO number |
| `etot` | string | Y | `09:10:00` | Estimated Takeoff Time |

### 4.3 Common `enRoute` Fields

| Field | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `seq` | integer | Y | `1` | Segment sequence number |
| `phase` | string | Y | `C` | Mission profile phase code |
| `startLLA` | object | Y | `{"lat": 37.480790, "lon": 126.878697, "alt": 50}` | Start coordinate |
| `endLLA` | object | Y | `{"lat": 37.480790, "lon": 126.884000, "alt": 300}` | End coordinate |
| `targetSpeed` | number | Y | `40` | Target speed, unit `m/s` |

### 4.4 `LLA` Coordinate Object

| Field | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `lat` | number | Y | `37.480790` | Latitude |
| `lon` | number | Y | `126.878697` | Longitude |
| `alt` | number | Y | `300` | Altitude, unit `m` |

### 4.5 Turn-Segment-Only Fields

Turn segments are only used when `phase` is `D` or `H`.

| Field | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `turnDirection` | string | Y | `CW` | Turn direction, `CW` or `CCW` |
| `centerLLA` | object | Y | `{"lat": 37.478000, "lon": 126.887500, "alt": 300}` | Turn center coordinate |

### 4.6 `arrival`

| Field | Type | Required | Example | Description |
| --- | --- | --- | --- | --- |
| `vertiport` | string | Y | `Jamsil` | Arrival vertiport |
| `sta` | string | Y | `10:00:00` | Scheduled Time of Arrival |
| `arrGateNumber` | string | Y | `G1` | Arrival gate number |
| `eibt` | string | Y | `09:58:00` | Estimated In-Block Time |
| `arrFatoNumber` | string | Y | `F1` | Arrival FATO number |
| `eldt` | string | Y | `09:50:00` | Estimated Landing Time |

## 5. Phase Rules

### 5.1 Non-Turn Segments

| Phase | Meaning | Fields | Example Behavior |
| --- | --- | --- | --- |
| `A` | gate out taxi | common fields only | Ground taxi from departure gate to departure FATO |
| `B` | vertical takeoff | common fields only | Vertical ascent from departure FATO |
| `C` | departure transition | common fields only | Initial outbound transition after takeoff |
| `E` | climb out | common fields only | Climb to cruise altitude |
| `F` | cruise | common fields only | Cruise along the main corridor |
| `G` | arrival transition | common fields only | Deceleration and inbound transition before arrival vertiport entry |
| `I` | final approach | common fields only | Final approach aligned to arrival FATO |
| `J` | landing | common fields only | Landing on arrival FATO |
| `K` | gate in taxi | common fields only when used | Ground taxi from arrival FATO to arrival gate |

### 5.2 Turn Segments

| Phase | Meaning | Additional Fields | Example Behavior |
| --- | --- | --- | --- |
| `D` | departure turn | `turnDirection`, `centerLLA` | Turn after departure to align with the corridor |
| `H` | arrival turn | `turnDirection`, `centerLLA` | Turn from the arrival corridor into the final approach heading |

### 5.3 Full `A~K` Mission Profile Example

| Seq | Phase | Example Description |
| --- | --- | --- |
| `1` | `A` | Taxi-out from `Yeouido G3` to `Yeouido F2` |
| `2` | `B` | Vertical takeoff from `Yeouido F2` |
| `3` | `C` | Enter departure transition segment |
| `4` | `D` | Align with the departure corridor through a turn segment |
| `5` | `E` | Climb out to cruise altitude |
| `6` | `F` | Cruise along the main corridor |
| `7` | `G` | Arrival transition toward `Jamsil` |
| `8` | `H` | Align to final heading through the arrival turn segment |
| `9` | `I` | Final approach to `Jamsil F1` |
| `10` | `J` | Land on `Jamsil F1` |
| `11` | `K` | Taxi-in from `Jamsil F1` to `Jamsil G1` |

## 6. Validation Rules

The following rules define a valid ICD record.

1. `flightPlanNumber` must be unique within the same batch.
2. `seq` must be continuous integers starting from `1`.
3. `phase` must use only defined codes.
4. If `phase` is not `D` or `H`, do not include `turnDirection` or `centerLLA`.
5. If `phase` is `D` or `H`, `turnDirection` and `centerLLA` are mandatory.
6. The recommended time order is `std <= eobt <= etot <= eldt <= eibt <= sta`.
7. All `LLA.alt` values must use the same unit, `m`.
8. `targetSpeed` must use the same unit, `m/s`, across all segments.
9. Segment coordinates should remain continuous whenever possible.

## 7. Example Data

### 7.1 Single JSON Example

```json
{
  "flightPlanNumber": 1201,
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "Yeouido",
    "std": "09:00:00",
    "depGateNumber": "G3",
    "eobt": "09:02:00",
    "depFatoNumber": "F2",
    "etot": "09:10:00"
  },
  "enRoute": [
    {
      "seq": 1,
      "phase": "A",
      "startLLA": {"lat": 37.525450, "lon": 126.921420, "alt": 0},
      "endLLA": {"lat": 37.525680, "lon": 126.922050, "alt": 0},
      "targetSpeed": 8
    },
    {
      "seq": 2,
      "phase": "B",
      "startLLA": {"lat": 37.525680, "lon": 126.922050, "alt": 0},
      "endLLA": {"lat": 37.525680, "lon": 126.922050, "alt": 60},
      "targetSpeed": 10
    },
    {
      "seq": 3,
      "phase": "C",
      "startLLA": {"lat": 37.525680, "lon": 126.922050, "alt": 60},
      "endLLA": {"lat": 37.524900, "lon": 126.928500, "alt": 180},
      "targetSpeed": 35
    },
    {
      "seq": 4,
      "phase": "D",
      "startLLA": {"lat": 37.524900, "lon": 126.928500, "alt": 180},
      "endLLA": {"lat": 37.521800, "lon": 126.944500, "alt": 180},
      "targetSpeed": 45,
      "turnDirection": "CW",
      "centerLLA": {"lat": 37.523000, "lon": 126.936000, "alt": 180}
    },
    {
      "seq": 5,
      "phase": "E",
      "startLLA": {"lat": 37.521800, "lon": 126.944500, "alt": 180},
      "endLLA": {"lat": 37.518000, "lon": 126.970000, "alt": 300},
      "targetSpeed": 55
    },
    {
      "seq": 6,
      "phase": "F",
      "startLLA": {"lat": 37.518000, "lon": 126.970000, "alt": 300},
      "endLLA": {"lat": 37.513500, "lon": 127.066000, "alt": 300},
      "targetSpeed": 75
    },
    {
      "seq": 7,
      "phase": "G",
      "startLLA": {"lat": 37.513500, "lon": 127.066000, "alt": 300},
      "endLLA": {"lat": 37.512500, "lon": 127.086500, "alt": 220},
      "targetSpeed": 45
    },
    {
      "seq": 8,
      "phase": "H",
      "startLLA": {"lat": 37.512500, "lon": 127.086500, "alt": 220},
      "endLLA": {"lat": 37.513900, "lon": 127.099000, "alt": 220},
      "targetSpeed": 35,
      "turnDirection": "CCW",
      "centerLLA": {"lat": 37.511800, "lon": 127.092800, "alt": 220}
    },
    {
      "seq": 9,
      "phase": "I",
      "startLLA": {"lat": 37.513900, "lon": 127.099000, "alt": 220},
      "endLLA": {"lat": 37.513650, "lon": 127.104200, "alt": 80},
      "targetSpeed": 22
    },
    {
      "seq": 10,
      "phase": "J",
      "startLLA": {"lat": 37.513650, "lon": 127.104200, "alt": 80},
      "endLLA": {"lat": 37.513600, "lon": 127.104500, "alt": 0},
      "targetSpeed": 8
    },
    {
      "seq": 11,
      "phase": "K",
      "startLLA": {"lat": 37.513600, "lon": 127.104500, "alt": 0},
      "endLLA": {"lat": 37.514020, "lon": 127.103950, "alt": 0},
      "targetSpeed": 6
    }
  ],
  "arrival": {
    "vertiport": "Jamsil",
    "sta": "10:00:00",
    "arrGateNumber": "G1",
    "eibt": "09:58:00",
    "arrFatoNumber": "F1",
    "eldt": "09:50:00"
  }
}
```

### 7.2 Test Data Summary

| flightPlanNumber | aircraftId | departure | arrival | std | sta |
| --- | --- | --- | --- | --- | --- |
| `1201` | `UAM0001` | `Yeouido` | `Jamsil` | `09:00:00` | `10:00:00` |
| `1202` | `UAM0002` | `Magok` | `Yeouido` | `09:15:00` | `09:55:00` |
| `1203` | `UAM0003` | `Jamsil` | `Incheon` | `10:10:00` | `10:55:00` |

## 8. Recommended Implementation Notes

- Build parsers and validators against the nested structure defined in this document.
- Even if CSV or legacy formats remain, unify the final internal representation to this JSON structure.
- Even if `MissionDispatch`, `MissionStatus`, and `SimClock` are later defined separately, the planning source of truth should remain the record structure defined here.
