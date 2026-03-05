import Foundation
import MapKit

struct Restaurant: Identifiable {
    let id: UUID
    let name: String
    let coordinate: CLLocationCoordinate2D
    let rating: Double
    let category: String
    let mapItem: MKMapItem

    init(from mapItem: MKMapItem) {
        self.id = UUID()
        self.mapItem = mapItem
        self.name = mapItem.name ?? "Unknown"
        self.coordinate = mapItem.placemark.coordinate

        // Synthesize rating deterministically from name hash (3.0–5.0)
        let hash = abs(self.name.hashValue)
        self.rating = 3.0 + Double(hash % 21) / 10.0

        // Extract category display name from point of interest category
        if let poiCategory = mapItem.pointOfInterestCategory {
            self.category = Self.displayName(for: poiCategory)
        } else {
            self.category = "Restaurant"
        }
    }

    private static func displayName(for category: MKPointOfInterestCategory) -> String {
        switch category {
        case .restaurant: return "Restaurant"
        case .cafe: return "Cafe"
        case .bakery: return "Bakery"
        case .brewery: return "Brewery"
        case .nightlife: return "Nightlife"
        case .foodMarket: return "Food Market"
        default: return "Restaurant"
        }
    }
}
