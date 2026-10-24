
import type {
  HistoricalRoadEvent,
  RankingRow,
} from '../domain/contracts';
import { REAL_CONTEXT } from './demoContext.real';

export type ExplainedRanking = RankingRow & {
  score_breakdown: {
    flood: number;
    access: number;
    property: number;
  };
  explanation: {
    flood: string;
    access: string;
    property: string;
  };
};

// DEMO assumptions, not measured accessibility or damage.

const DEMO_CONTEXT: Record<string, {
  accessPoints: number;
  propertyPoints: number;
  accessNote: string;
  propertyNote: string;
}> = {
  'fixture:morrissey-boulevard': {
    accessPoints: 35,
    propertyPoints: 18,
    accessNote:
      'Major north-south corridor through Dorchester and Columbia Point, ' +
      'providing access toward UMass Boston and surrounding neighborhoods. ' +
      'Nearby emergency-response infrastructure includes Boston Fire Engine 17 / Ladder 7. ' +
      'The score is illustrative; actual facility routes and population served are not calculated.',
    propertyNote:
      'Potential exposure includes roadside businesses, buildings, parked vehicles, ' +
      'traffic signals and other public infrastructure. ' +
      'No verified property-loss or crash count is assigned.',
  },

  'fixture:day-boulevard': {
    accessPoints: 30,
    propertyPoints: 17,
    accessNote:
      'Coastal roadway serving South Boston waterfront recreation, ' +
      'beach access and surrounding residential streets. ' +
      'Flood disruption could affect local access and require alternative streets. ' +
      'Actual detours and the number of affected residents are not measured.',
    propertyNote:
      'Potentially exposed assets include waterfront recreation facilities, ' +
      'park infrastructure, roadside equipment, vehicles and nearby properties. ' +
      'These are illustrative exposure categories, not recorded damage.',
  },

  'fixture:mount-vernon': {
    accessPoints: 28,
    propertyPoints: 15,
    accessNote:
      'Local connector serving Columbia Point, UMass Boston-area destinations ' +
      'and neighborhood access. It is relevant to investigating access ' +
      'between residential areas and the peninsula. ' +
      'No route-dependency or population calculation has been performed.',
    propertyNote:
      'Potential exposure categories include buildings, parking areas, ' +
      'traffic controls, sidewalks and vehicles. ' +
      'The property weighting is illustrative, without a verified asset-loss estimate.',
  },

  'fixture:inland-control': {
    accessPoints: 15,
    propertyPoints: 7,
    accessNote:
      'Illustrative inland comparison corridor with lower assumed ' +
      'dependency on essential services. No population or routing analysis was performed.',
    propertyNote:
      'Illustrative lower property-exposure weighting. ' +
      'No verified asset damage inventory is available.',
  },
};


export function rankPersonOne(
  rows: RankingRow[],
  events: HistoricalRoadEvent[]
): ExplainedRanking[] {
  const scored = rows.map((row) => {
    // Computed values (Person 3) replace the illustrative DEMO_CONTEXT; DEMO_CONTEXT stays as a fallback.
    const context = REAL_CONTEXT[row.corridor_id] ?? DEMO_CONTEXT[row.corridor_id] ?? {
      accessPoints: 0,
      propertyPoints: 0,
      accessNote: 'Critical-access assessment unavailable.',
      propertyNote: 'Property-exposure assessment unavailable.',
    };

    const matchingEvents = events.filter((event) =>
      row.road_ids.some((id) =>
        event.affected_road_ids.includes(id)
      )
    );

    // Up to 30 points from the two loaded historical events.
    const floodPoints =
      events.length > 0
        ? Math.round(
          (matchingEvents.length / events.length) * 30
        )
        : 0;

    const total =
      floodPoints +
      context.accessPoints +
      context.propertyPoints;

    return {
      ...row,
      impact_value: total,
      impact_units: 'demo priority points / 100',
      score_breakdown: {
        flood: floodPoints,
        access: context.accessPoints,
        property: context.propertyPoints,
      },
      explanation: {
        flood:
          row.corridor_id === 'fixture:morrissey-boulevard'
            ? 'Since 2006, Boston Harbor reached the level at which Morrissey Boulevard floods on 167 days, including 12 major high-water events (NOAA Boston gauge).'
            : `${matchingEvents.length} of ${events.length} loaded past floods overlap this corridor${matchingEvents.length ? `: ${matchingEvents.map((event) => event.date_label).join(', ')}` : ''}.`,
        access: context.accessNote,
        property: context.propertyNote,
      },
      assumptions: [
        'Weighting: flood 30%, critical access 45%, property exposure 25%.',
        REAL_CONTEXT[row.corridor_id]
          ? 'Access = network accessibility loss on the OSM graph (assumed journeys, extent overlap treated as closure); property = building footprints near the corridor inside the MC-FRM 2050 extent. Both scaled to the max among ranked corridors.'
          : 'Critical-access and property scores are illustrative inputs.',
        'Flood exposure does not establish road closure or damage.',
      ],
    };
  });

  return scored
    .sort((a, b) => (b.impact_value ?? 0) - (a.impact_value ?? 0))
    .map((row, index) => ({
      ...row,
      priority_rank: index + 1,
    }));
}
