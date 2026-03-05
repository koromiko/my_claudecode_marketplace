import SwiftUI
import MapKit

@Observable
@MainActor
final class ExploreViewModel {
    var restaurants: [Restaurant] = []
    var isLoading = false
    var errorMessage: String?
    var cameraPosition: MapCameraPosition

    private var searchTask: Task<Void, Never>?
    private var lastCenter: CLLocationCoordinate2D?

    private static let defaultCenter = CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194)
    private static let defaultSpan = MKCoordinateSpan(latitudeDelta: 0.05, longitudeDelta: 0.05)

    init() {
        let region = MKCoordinateRegion(center: Self.defaultCenter, span: Self.defaultSpan)
        self.cameraPosition = .region(region)
    }

    func onRegionChange(_ region: MKCoordinateRegion) {
        searchTask?.cancel()
        searchTask = Task {
            do {
                try await Task.sleep(for: .milliseconds(500))
            } catch {
                return // Cancelled during debounce
            }

            // Epsilon check — skip if region barely changed
            if let last = lastCenter {
                let latDelta = abs(region.center.latitude - last.latitude)
                let lonDelta = abs(region.center.longitude - last.longitude)
                if latDelta < 0.001 && lonDelta < 0.001 {
                    return
                }
            }

            lastCenter = region.center
            await searchRestaurants(in: region)
        }
    }

    func searchRestaurants(in region: MKCoordinateRegion) async {
        isLoading = true
        errorMessage = nil

        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = "restaurants"
        request.region = region

        let search = MKLocalSearch(request: request)

        do {
            let response = try await search.start()
            restaurants = response.mapItems
                .map { Restaurant(from: $0) }
                .sorted { $0.rating > $1.rating }
        } catch {
            if !Task.isCancelled {
                errorMessage = error.localizedDescription
            }
        }

        isLoading = false
    }

    func performInitialSearch() {
        let region = MKCoordinateRegion(center: Self.defaultCenter, span: Self.defaultSpan)
        searchTask = Task {
            await searchRestaurants(in: region)
        }
    }
}
