import { Card, CardContent } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen w-full items-center justify-center bg-gray-50">
      <section className="w-full max-w-md mx-4">
        <Card>
          <CardContent className="pt-6">
            <header className="mb-4 flex gap-2">
              <AlertCircle className="h-8 w-8 text-red-500" />
              <h1 className="text-2xl font-bold text-gray-900">404 Page Not Found</h1>
            </header>

            <p className="mt-4 text-sm text-gray-600">
              Did you forget to add the page to the router?
            </p>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
